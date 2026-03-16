import re


class ParsedExercise:
    def __init__(self, exercise_id, exercise_name):
        self.exercise_id = exercise_id
        self.exercise_name = exercise_name
        self.sets = []  # List of (weight, reps) tuples
        self.skipped = False
        self.as_planned = False
        self.confidence = 'high'
        self.raw_text = ''


class ParseResult:
    def __init__(self):
        self.exercises = []
        self.overall_confidence = 'high'
        self.unmatched_lines = []


# Regex patterns for German workout replies
PATTERNS = {
    # "80/80/85 je 8" → weights vary, reps shared
    'weights_shared_reps': re.compile(
        r'(\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)+)\s*(?:je|x|mal)\s*(\d+)',
        re.IGNORECASE
    ),
    # "3x8 @ 80kg" or "3x8 80kg"
    'sets_x_reps_at_weight': re.compile(
        r'(\d+)\s*[xX×]\s*(\d+)\s*(?:@|bei|mit)?\s*(\d+(?:[.,]\d+)?)\s*(?:kg)?',
        re.IGNORECASE
    ),
    # "3x8" without weight
    'sets_x_reps': re.compile(
        r'(\d+)\s*[xX×]\s*(\d+)(?!\s*(?:@|bei|mit|\d))',
        re.IGNORECASE
    ),
    # "60kg 10/10/8" → weight shared, reps vary
    'weight_then_reps': re.compile(
        r'(\d+(?:[.,]\d+)?)\s*(?:kg)\s+(\d+(?:\s*/\s*\d+)+)',
        re.IGNORECASE
    ),
    # "10/10/8 @ 60kg" or "10/10/8 60kg"
    'reps_then_weight': re.compile(
        r'(\d+(?:\s*/\s*\d+)+)\s*(?:@|bei|mit)?\s*(\d+(?:[.,]\d+)?)\s*(?:kg)',
        re.IGNORECASE
    ),
    # "wie geplant" / "geschafft" → use target values
    'as_planned': re.compile(
        r'(?:wie\s*geplant|geschafft|alles\s*geschafft|passt|erledigt)',
        re.IGNORECASE
    ),
    # "übersprungen" / "nicht gemacht" / "skip"
    'skipped': re.compile(
        r'(?:übersprungen|nicht\s*gemacht|skip|ausgelassen|weggelassen)',
        re.IGNORECASE
    ),
    # "geschafft aber nur 2 Sätze"
    'partial': re.compile(
        r'(?:geschafft|gemacht).*?(?:nur|aber)\s*(\d+)\s*(?:Sätze?|Sets?)',
        re.IGNORECASE
    ),
}


def parse_workout_reply(text, routine_exercises):
    """
    Parse a trainee's email reply into workout data.

    Args:
        text: Clean reply text (quoted text already stripped)
        routine_exercises: List of dicts with exercise_id, exercise_name/name,
                          target_sets, target_reps, target_weight, position

    Returns:
        ParseResult with parsed exercises
    """
    result = ParseResult()
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]

    if not routine_exercises:
        result.overall_confidence = 'low'
        return result

    # Normalize exercise names
    for ex in routine_exercises:
        if 'exercise_name' not in ex and 'name' in ex:
            ex['exercise_name'] = ex['name']

    full_text = text.strip().lower()

    # Check for global "wie geplant"
    if PATTERNS['as_planned'].search(full_text) and len(lines) <= 2:
        for rex in routine_exercises:
            pe = ParsedExercise(rex['exercise_id'], rex.get('exercise_name', ''))
            pe.as_planned = True
            for _ in range(rex.get('target_sets') or 3):
                pe.sets.append((rex.get('target_weight'), rex.get('target_reps', 10)))
            result.exercises.append(pe)
        return result

    # Check for global "übersprungen"
    if PATTERNS['skipped'].search(full_text) and len(lines) <= 2:
        for rex in routine_exercises:
            pe = ParsedExercise(rex['exercise_id'], rex.get('exercise_name', ''))
            pe.skipped = True
            result.exercises.append(pe)
        return result

    # Try positional matching (line count == exercise count)
    if len(lines) == len(routine_exercises):
        for i, line in enumerate(lines):
            pe = _parse_line(line, routine_exercises[i])
            result.exercises.append(pe)
    elif len(lines) > 0:
        # Try name-based matching first, then positional for remainder
        used_exercises = set()
        unmatched_lines = []

        for line in lines:
            matched = False
            for rex in routine_exercises:
                if rex['exercise_id'] in used_exercises:
                    continue
                if _name_matches(rex.get('exercise_name', ''), line):
                    pe = _parse_line(line, rex)
                    result.exercises.append(pe)
                    used_exercises.add(rex['exercise_id'])
                    matched = True
                    break
            if not matched:
                unmatched_lines.append(line)

        # Positional fallback for unmatched lines
        remaining = [r for r in routine_exercises if r['exercise_id'] not in used_exercises]
        for i, line in enumerate(unmatched_lines):
            if i < len(remaining):
                pe = _parse_line(line, remaining[i])
                pe.confidence = 'medium'
                result.exercises.append(pe)
            else:
                result.unmatched_lines.append(line)

    # Calculate overall confidence
    confidences = [pe.confidence for pe in result.exercises]
    if 'low' in confidences or result.unmatched_lines:
        result.overall_confidence = 'low'
    elif 'medium' in confidences:
        result.overall_confidence = 'medium'

    return result


def _parse_line(line, routine_exercise):
    """Parse a single line against a known exercise."""
    pe = ParsedExercise(
        routine_exercise['exercise_id'],
        routine_exercise.get('exercise_name', '')
    )
    pe.raw_text = line

    target_sets = routine_exercise.get('target_sets') or 3
    target_reps = routine_exercise.get('target_reps') or 10
    target_weight = routine_exercise.get('target_weight')

    # Special cases first
    if PATTERNS['skipped'].search(line):
        pe.skipped = True
        return pe

    # Partial must be checked before as_planned (both match "geschafft")
    m = PATTERNS['partial'].search(line)
    if m:
        num_sets = int(m.group(1))
        for _ in range(min(num_sets, target_sets)):
            pe.sets.append((target_weight, target_reps))
        return pe

    if PATTERNS['as_planned'].search(line):
        pe.as_planned = True
        for _ in range(target_sets):
            pe.sets.append((target_weight, target_reps))
        return pe

    # "80/80/85 je 8"
    m = PATTERNS['weights_shared_reps'].search(line)
    if m:
        weights = [float(w.strip().replace(',', '.')) for w in m.group(1).split('/')]
        reps = int(m.group(2))
        for w in weights:
            pe.sets.append((w, reps))
        return pe

    # "3x8 @ 80kg"
    m = PATTERNS['sets_x_reps_at_weight'].search(line)
    if m:
        num_sets = int(m.group(1))
        reps = int(m.group(2))
        weight = float(m.group(3).replace(',', '.'))
        for _ in range(num_sets):
            pe.sets.append((weight, reps))
        return pe

    # "60kg 10/10/8"
    m = PATTERNS['weight_then_reps'].search(line)
    if m:
        weight = float(m.group(1).replace(',', '.'))
        reps_list = [int(r.strip()) for r in m.group(2).split('/')]
        for r in reps_list:
            pe.sets.append((weight, r))
        return pe

    # "10/10/8 @ 60kg"
    m = PATTERNS['reps_then_weight'].search(line)
    if m:
        reps_list = [int(r.strip()) for r in m.group(1).split('/')]
        weight = float(m.group(2).replace(',', '.'))
        for r in reps_list:
            pe.sets.append((weight, r))
        return pe

    # "3x8" without weight
    m = PATTERNS['sets_x_reps'].search(line)
    if m:
        num_sets = int(m.group(1))
        reps = int(m.group(2))
        for _ in range(num_sets):
            pe.sets.append((target_weight, reps))
        return pe

    # Could not parse
    pe.confidence = 'low'
    return pe


def _name_matches(exercise_name, line):
    """Check if exercise name (or significant parts) appears in line."""
    if not exercise_name:
        return False
    name_lower = exercise_name.lower()
    line_lower = line.lower()

    if name_lower in line_lower:
        return True

    # Match significant words (>3 chars)
    words = [w.strip('()') for w in name_lower.split() if len(w.strip('()')) > 3]
    for word in words:
        if word in line_lower:
            return True

    return False

// ── Theme Toggle ───────────────────────────────────

function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme') || 'light';
    const next = current === 'light' ? 'dark' : 'light';
    html.setAttribute('data-theme', next);
    localStorage.setItem('fittrack-theme', next);
}

// Apply saved theme
(function() {
    const saved = localStorage.getItem('fittrack-theme');
    if (saved) document.documentElement.setAttribute('data-theme', saved);
})();


// ── Workout Timer ──────────────────────────────────

(function() {
    const timerEl = document.getElementById('workout-timer');
    if (!timerEl) return;

    const started = new Date(timerEl.dataset.started);

    function updateTimer() {
        const now = new Date();
        const diff = Math.floor((now - started) / 1000);
        const h = Math.floor(diff / 3600);
        const m = Math.floor((diff % 3600) / 60);
        const s = diff % 60;
        if (h > 0) {
            timerEl.textContent = `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        } else {
            timerEl.textContent = `${m}:${String(s).padStart(2, '0')}`;
        }
    }

    updateTimer();
    setInterval(updateTimer, 1000);
})();


// ── Exercise Picker Modal ──────────────────────────

function openExercisePicker() {
    const overlay = document.getElementById('modal-overlay');
    const content = document.getElementById('modal-content');
    if (!overlay || !content) return;

    const workoutId = window.WORKOUT_ID;
    // Fetch picker content
    fetch(`/api/exercise-picker?workout_id=${workoutId}`)
        .then(r => r.text())
        .then(html => {
            content.innerHTML = html;
            htmx.process(content);
            overlay.classList.add('active');
            // Auto-focus search
            const search = content.querySelector('#exercise-search');
            if (search) search.focus();
        });
}

function closeModal() {
    const overlay = document.getElementById('modal-overlay');
    if (overlay) overlay.classList.remove('active');
}


// ── Exercise Picker: Filter & Add ──────────────────

function filterExercises() {
    const search = (document.getElementById('exercise-search').value || '').toLowerCase();
    const group = document.getElementById('exercise-filter-group').value;
    document.querySelectorAll('#exercise-picker-list .exercise-list-item').forEach(li => {
        const name = li.dataset.name || '';
        const muscle = li.dataset.muscle || '';
        const matchSearch = !search || name.includes(search);
        const matchGroup = !group || muscle === group;
        li.style.display = (matchSearch && matchGroup) ? '' : 'none';
    });
}

function addExerciseToWorkout(workoutId, exerciseId, el) {
    el.style.opacity = '0.5';
    el.style.pointerEvents = 'none';
    fetch(`/workout/${workoutId}/add-exercise`, {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: `exercise_id=${exerciseId}`
    })
    .then(r => r.text())
    .then(html => {
        document.getElementById('exercise-list').insertAdjacentHTML('beforeend', html);
        htmx.process(document.getElementById('exercise-list'));
        closeModal();
    });
}


// ── Icon Picker (Notion-style) ────────────────────

const ICON_EMOJIS = [
    '💪', '🏋️', '🏃', '🔥', '⚡', '🎯', '🏆', '💥', '🦾', '🧠',
    '❤️', '🌟', '✨', '🚀', '🏅', '🥇', '💎', '🎖️', '⭐', '🌊',
    '🏔️', '🐺', '🦁', '🐻', '🦅', '🐉', '🏛️', '⚔️', '🛡️', '🎪',
    '🍏', '🥑', '🥩', '🥗', '💊', '🧬', '🔬', '📈', '📊', '🗓️'
];

function openIconPicker(e) {
    e.preventDefault();
    e.stopPropagation();
    const picker = document.getElementById('icon-picker');
    if (!picker) return;

    if (picker.style.display !== 'none') {
        picker.style.display = 'none';
        return;
    }

    const grid = document.getElementById('icon-picker-grid');
    grid.innerHTML = ICON_EMOJIS.map(em =>
        `<button type="button" class="icon-picker-item" onclick="selectIcon('${em}')">${em}</button>`
    ).join('') + '<button type="button" class="icon-picker-item icon-picker-remove" onclick="selectIcon(\'\')">&#10005;</button>';
    picker.style.display = 'block';
}

function selectIcon(icon) {
    document.getElementById('logo-icon').textContent = icon || '\u2696';
    document.getElementById('icon-picker').style.display = 'none';
    fetch('/api/app-icon', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: `icon=${encodeURIComponent(icon)}`
    });
}

document.addEventListener('click', function(e) {
    const picker = document.getElementById('icon-picker');
    if (picker && picker.style.display !== 'none') {
        if (!e.target.closest('#icon-picker') && !e.target.closest('#logo-icon')) {
            picker.style.display = 'none';
        }
    }
});


// ── Keyboard Shortcuts ─────────────────────────────

document.addEventListener('keydown', function(e) {
    // Escape: close modal & icon picker
    if (e.key === 'Escape') {
        closeModal();
        const picker = document.getElementById('icon-picker');
        if (picker) picker.style.display = 'none';
    }
});

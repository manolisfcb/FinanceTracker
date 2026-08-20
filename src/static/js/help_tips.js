// Click/tap handling for .tn-help "?" icons. Hover and keyboard focus are
// handled in CSS; this exists so the explanations are reachable on touch
// devices, where hover never fires.
(function () {
    function closeAll(except) {
        document.querySelectorAll('.tn-help.is-open').forEach(function (tip) {
            if (tip !== except) {
                tip.classList.remove('is-open');
            }
        });
    }

    document.addEventListener('click', function (event) {
        var trigger = event.target.closest('.tn-help');
        closeAll(trigger);
        if (trigger) {
            // Only one open at a time, and a second tap on the same icon
            // closes it again.
            trigger.classList.toggle('is-open');
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            closeAll(null);
        }
    });
})();

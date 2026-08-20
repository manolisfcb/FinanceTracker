// Tooltip handling for .tn-help "?" icons. Visible bubbles are portalled to
// <body> so Chromium's multicolumn layout cannot fragment them across columns.
(function () {
    var bubbles = new WeakMap();
    var activeTrigger = null;
    var pinnedTrigger = null;
    var nextBubbleId = 0;

    document.querySelectorAll('.tn-help').forEach(function (trigger) {
        var bubble = trigger.querySelector('.tn-help-bubble');
        if (!bubble) return;

        if (!bubble.id) {
            nextBubbleId += 1;
            bubble.id = 'tn-help-bubble-' + nextBubbleId;
        }
        trigger.setAttribute('aria-describedby', bubble.id);
        bubbles.set(trigger, bubble);
        document.body.appendChild(bubble);
    });

    function positionBubble(trigger, bubble) {
        var gap = 8;
        var viewportPadding = 12;
        var triggerRect = trigger.getBoundingClientRect();
        var bubbleRect = bubble.getBoundingClientRect();
        var left = triggerRect.left + (triggerRect.width - bubbleRect.width) / 2;
        var maxLeft = window.innerWidth - viewportPadding - bubbleRect.width;

        left = Math.max(viewportPadding, Math.min(left, maxLeft));

        var top = triggerRect.top - bubbleRect.height - gap;
        if (top < viewportPadding) {
            top = triggerRect.bottom + gap;
        }
        if (top + bubbleRect.height > window.innerHeight - viewportPadding) {
            top = Math.max(viewportPadding, window.innerHeight - viewportPadding - bubbleRect.height);
        }

        bubble.style.left = Math.round(left) + 'px';
        bubble.style.top = Math.round(top) + 'px';
    }

    function hideActive() {
        if (!activeTrigger) return;

        var bubble = bubbles.get(activeTrigger);
        if (bubble) bubble.classList.remove('is-visible');
        activeTrigger = null;
    }

    function show(trigger) {
        var bubble = bubbles.get(trigger);
        if (!bubble) return;

        if (activeTrigger !== trigger) hideActive();
        activeTrigger = trigger;
        bubble.style.visibility = 'hidden';
        bubble.classList.add('is-visible');
        positionBubble(trigger, bubble);
        bubble.style.visibility = '';
    }

    function clearPinned() {
        if (!pinnedTrigger) return;
        pinnedTrigger.classList.remove('is-open');
        pinnedTrigger = null;
    }

    function restorePinnedOrHide() {
        if (pinnedTrigger) show(pinnedTrigger);
        else hideActive();
    }

    document.addEventListener('click', function (event) {
        var trigger = event.target.closest('.tn-help');
        if (trigger) {
            if (pinnedTrigger === trigger) {
                clearPinned();
                hideActive();
                return;
            }

            clearPinned();
            pinnedTrigger = trigger;
            trigger.classList.add('is-open');
            show(trigger);
            return;
        }

        clearPinned();
        hideActive();
    });

    document.addEventListener('mouseover', function (event) {
        var trigger = event.target.closest('.tn-help');
        if (trigger) show(trigger);
    });

    document.addEventListener('mouseout', function (event) {
        var trigger = event.target.closest('.tn-help');
        if (!trigger || trigger.contains(event.relatedTarget)) return;
        if (pinnedTrigger !== trigger && document.activeElement !== trigger) {
            restorePinnedOrHide();
        }
    });

    document.addEventListener('focusin', function (event) {
        var trigger = event.target.closest('.tn-help');
        if (trigger) show(trigger);
    });

    document.addEventListener('focusout', function (event) {
        var trigger = event.target.closest('.tn-help');
        if (trigger && pinnedTrigger !== trigger) restorePinnedOrHide();
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            clearPinned();
            hideActive();
        }
    });

    window.addEventListener('resize', function () {
        if (activeTrigger) positionBubble(activeTrigger, bubbles.get(activeTrigger));
    });

    window.addEventListener('scroll', function () {
        if (activeTrigger) positionBubble(activeTrigger, bubbles.get(activeTrigger));
    }, true);
})();

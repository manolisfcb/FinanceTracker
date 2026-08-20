// Whole-row / whole-card navigation: anything carrying data-row-href opens
// that URL when clicked.
//
// The visible <a> inside the row stays exactly as it was — it is what a
// keyboard, a screen reader and a middle click follow. This only widens the
// hit area for a pointer, and it steps aside for anything that is already
// interactive or when the "click" was really the end of a text selection.
//
// Delegated from the document so it keeps working after HTMX swaps a table
// or a card grid out from under it.
(function () {
    var INTERACTIVE = 'a, button, input, select, textarea, summary, label, [role="button"]';

    document.addEventListener('click', function (event) {
        if (event.defaultPrevented || event.button !== 0) {
            return;
        }
        var row = event.target.closest('[data-row-href]');
        if (!row || event.target.closest(INTERACTIVE)) {
            return;
        }
        // Selecting a ticker to copy it shouldn't navigate away.
        var selection = window.getSelection();
        if (selection && String(selection).length > 0) {
            return;
        }

        var href = row.getAttribute('data-row-href');
        if (event.metaKey || event.ctrlKey || event.shiftKey) {
            window.open(href, '_blank');
        } else {
            window.location.href = href;
        }
    });
})();

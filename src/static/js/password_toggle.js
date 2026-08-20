// Show/hide for a password field. Progressive enhancement: without JS the
// field is still a normal password input, just permanently masked.
document.querySelectorAll('[data-password-toggle]').forEach(function (button) {
    var input = document.getElementById(button.dataset.passwordToggle);
    if (!input) return;

    button.setAttribute('aria-label', 'Mostrar la contraseña');
    button.addEventListener('click', function () {
        var revealed = input.type === 'text';
        input.type = revealed ? 'password' : 'text';
        button.textContent = revealed ? 'Mostrar' : 'Ocultar';
        button.setAttribute(
            'aria-label',
            revealed ? 'Mostrar la contraseña' : 'Ocultar la contraseña'
        );
        // Typing should continue where it left off, not at position zero.
        input.focus();
        var end = input.value.length;
        input.setSelectionRange(end, end);
    });
});

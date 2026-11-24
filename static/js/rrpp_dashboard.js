document.addEventListener('DOMContentLoaded', function () {
    const btnGenerarPases = document.getElementById('btnGenerarPases');
    const modalSinEventoEl = document.getElementById('modalSinEvento');
    const modalPaseEl = document.getElementById('modalPase');
    const formPase = document.getElementById('formGenerarPase');

    if (btnGenerarPases) {
        btnGenerarPases.addEventListener('click', function () {
            const hayEventoActivo = btnGenerarPases.dataset.hayEvento === '1';
            const eventoVencido = btnGenerarPases.dataset.vencido === '1';

            if (!hayEventoActivo || eventoVencido) {
                if (modalSinEventoEl) {
                    bootstrap.Modal.getOrCreateInstance(modalSinEventoEl).show();
                }
            } else if (modalPaseEl) {
                bootstrap.Modal.getOrCreateInstance(modalPaseEl).show();
            }
        });
    }

    if (formPase) {
        formPase.addEventListener('submit', function (e) {
            e.preventDefault();

            const submitBtn = formPase.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
            }

            const datos = {
                nombre: document.getElementById('nombre').value,
                dni: document.getElementById('dni').value,
                whatsapp: document.getElementById('whatsapp').value,
                cantidad: document.getElementById('cantidad').value
            };

            fetch('/rrpp/generar_pase', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(datos)
            })
                .then(function (res) {
                    return res.json();
                })
                .then(function (data) {
                    if (data.success) {
                        window.open(data.link_whatsapp, '_blank');
                        location.reload();
                    } else {
                        alert(data.error || 'Error al generar el pase.');
                        if (submitBtn) {
                            submitBtn.disabled = false;
                        }
                    }
                })
                .catch(function (err) {
                    console.error(err);
                    alert('Error de conexión.');
                    if (submitBtn) {
                        submitBtn.disabled = false;
                    }
                });
        });
    }
});
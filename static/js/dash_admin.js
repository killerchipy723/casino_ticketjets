 document.getElementById('formGenerarPase').addEventListener('submit', function(e) {
        e.preventDefault();
        
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
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // Abrir WhatsApp automáticamente con el mensaje y link del PDF
                window.open(data.link_whatsapp, '_blank');
                location.reload(); // Recargar para ver el ticket en la tabla
            } else {
                alert(data.error || 'Error al generar el pase.');
            }
        })
        .catch(err => {
            console.error(err);
            alert('Error de conexión.');
        });
    });
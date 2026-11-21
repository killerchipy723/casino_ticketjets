document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('preview');
    const canvasElement = document.getElementById('canvas');
    const canvas = canvasElement ? canvasElement.getContext('2d', { willReadFrequently: true }) : null;
    const videoContainer = document.getElementById('video-container');
    const btnIniciarContainer = document.getElementById('btn-iniciar-container');
    const btnDetenerContainer = document.getElementById('btn-detener-container');
    const btnIniciarCamara = document.getElementById('btnIniciarCamara');
    const btnDetenerCamara = document.getElementById('btnDetenerCamara');
    const formCodigoPuerta = document.getElementById('formCodigoPuerta');
    const codigoInput = document.getElementById('codigoInput');

    let scanning = false;
    let currentStream = null;

    function resolverDestinoCodigo(rawData) {
        let textoQR = (rawData || '').trim();
        if (!textoQR) return null;

        if (textoQR.includes('codigo_qr=')) {
            try {
                const urlObj = new URL(textoQR);
                const paramQr = urlObj.searchParams.get('codigo_qr');
                if (paramQr) textoQR = paramQr.trim();
            } catch (_) {
                // Continuar con procesamiento de texto si no es URL completa
            }
        } else if (textoQR.includes('/')) {
            const partes = textoQR.split('/').filter(Boolean);
            textoQR = partes[partes.length - 1];
        }

        const codigoNormalizado = textoQR.toUpperCase();
        if (codigoNormalizado.startsWith('CUMP-')) {
            return `/portero/cumpleanos?codigo_qr=${encodeURIComponent(codigoNormalizado)}`;
        }
        return `/admin/validar/${encodeURIComponent(textoQR)}`;
    }

    function detenerCamara() {
        scanning = false;
        if (currentStream) {
            currentStream.getTracks().forEach((track) => track.stop());
            currentStream = null;
        }
        if (video) video.srcObject = null;
        if (videoContainer) videoContainer.style.display = 'none';
        if (btnDetenerContainer) btnDetenerContainer.style.display = 'none';
        if (btnIniciarContainer) btnIniciarContainer.style.display = 'block';
    }

    function tick() {
        if (!scanning || !video || !canvas || !canvasElement) return;

        if (video.readyState === video.HAVE_ENOUGH_DATA) {
            canvasElement.height = video.videoHeight;
            canvasElement.width = video.videoWidth;
            canvas.drawImage(video, 0, 0, canvasElement.width, canvasElement.height);

            const imageData = canvas.getImageData(0, 0, canvasElement.width, canvasElement.height);
            const code = typeof jsQR === 'function'
                ? jsQR(imageData.data, imageData.width, imageData.height, { inversionAttempts: 'dontInvert' })
                : null;

            if (code && code.data) {
                const destino = resolverDestinoCodigo(code.data);
                detenerCamara();
                if (destino) {
                    window.location.href = destino;
                }
                return;
            }
        }
        requestAnimationFrame(tick);
    }

    function iniciarCamara() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('No se pudo acceder a la cámara. Usa el ingreso manual.');
            return;
        }

        if (btnIniciarContainer) btnIniciarContainer.style.display = 'none';
        if (videoContainer) videoContainer.style.display = 'block';
        if (btnDetenerContainer) btnDetenerContainer.style.display = 'block';
        scanning = true;

        navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
            .then((stream) => {
                currentStream = stream;
                video.srcObject = stream;
                video.setAttribute('playsinline', true);
                video.play();
                requestAnimationFrame(tick);
            })
            .catch((err) => {
                console.error('Error al acceder a la cámara: ', err);
                alert('No se pudo acceder a la cámara. Usa el ingreso manual.');
                detenerCamara();
            });
    }

    if (btnIniciarCamara) {
        btnIniciarCamara.addEventListener('click', iniciarCamara);
    }
    if (btnDetenerCamara) {
        btnDetenerCamara.addEventListener('click', detenerCamara);
    }
    if (formCodigoPuerta && codigoInput) {
        formCodigoPuerta.addEventListener('submit', (e) => {
            e.preventDefault();
            const destino = resolverDestinoCodigo(codigoInput.value);
            if (destino) {
                window.location.href = destino;
            }
        });
    }
});
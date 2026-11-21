document.addEventListener('DOMContentLoaded', () => {
  const tarjeta = document.getElementById('tarjetaQr');
  const container = document.getElementById('qrCanvasContainer');
  const btnPng = document.getElementById('btnDescargarPng');

  if (!tarjeta || !container || typeof QRCode === 'undefined') return;

  const codigoQr = (tarjeta.dataset.codigoQr || '').trim();
  if (!codigoQr) return;

  container.innerHTML = '';
  new QRCode(container, {
    text: codigoQr,
    width: 190,
    height: 190,
    correctLevel: QRCode.CorrectLevel.M
  });

  if (btnPng) {
    btnPng.addEventListener('click', () => {
      const canvas = container.querySelector('canvas');
      const img = container.querySelector('img');
      let dataUrl = null;

      if (canvas) {
        dataUrl = canvas.toDataURL('image/png');
      } else if (img && img.src) {
        dataUrl = img.src;
      }

      if (!dataUrl) {
        alert('No se pudo generar la imagen del QR.');
        return;
      }

      const link = document.createElement('a');
      link.href = dataUrl;
      link.download = `QR_${codigoQr}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    });
  }
});
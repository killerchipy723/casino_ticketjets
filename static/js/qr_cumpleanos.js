document.addEventListener('DOMContentLoaded', () => {
  const tarjeta = document.getElementById('tarjetaQr');
  const container = document.getElementById('qrCanvasContainer');
  if (!tarjeta || !container || typeof QRCode === 'undefined') return;

  const codigoQr = tarjeta.dataset.codigoQr;
  if (!codigoQr) return;

  container.innerHTML = '';
  new QRCode(container, {
    text: codigoQr,
    width: 190,
    height: 190,
    correctLevel: QRCode.CorrectLevel.M
  });
});
document.addEventListener('DOMContentLoaded', () => {
  const botonesCopiar = document.querySelectorAll('.btn-copiar-link');

  botonesCopiar.forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.dataset.target;
      const elemento = document.getElementById(targetId);
      if (!elemento) return;

      const texto = elemento.innerText.trim();
      navigator.clipboard.writeText(texto).then(() => {
        const textoOriginal = btn.innerText;
        btn.innerText = '¡Copiado!';
        setTimeout(() => {
          btn.innerText = textoOriginal;
        }, 1600);
      });
    });
  });

  const formFiltro = document.getElementById('formFiltroCumpleanos');
  const combosFiltro = document.querySelectorAll('#filtroEvento, #filtroEstado');

  if (formFiltro && combosFiltro.length > 0) {
    combosFiltro.forEach((combo) => {
      combo.addEventListener('change', () => {
        if (typeof formFiltro.requestSubmit === 'function') {
          formFiltro.requestSubmit();
        } else {
          formFiltro.submit();
        }
      });
    });
  }
});
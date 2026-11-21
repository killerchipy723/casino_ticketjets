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
});
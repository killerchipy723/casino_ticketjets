document.addEventListener('DOMContentLoaded', () => {
  const formAprobar = document.getElementById('formAprobarCumple');
  if (!formAprobar) return;

  const limiteAmigos = parseInt(formAprobar.dataset.limiteAmigos || '0', 10);
  const yaIngresados = parseInt(formAprobar.dataset.yaIngresados || '0', 10);
  const cuposNumEl = document.getElementById('cuposRestantesNum');
  const checkboxesAmigos = Array.from(formAprobar.querySelectorAll('.chk-amigo:not(:disabled)'));

  function actualizarCupos() {
    const nuevosMarcados = checkboxesAmigos.filter((chk) => chk.checked).length;
    const restantes = Math.max(0, limiteAmigos - yaIngresados - nuevosMarcados);
    if (cuposNumEl) {
      cuposNumEl.innerText = restantes;
    }
  }

  checkboxesAmigos.forEach((chk) => {
    chk.addEventListener('change', actualizarCupos);
  });
  actualizarCupos();
});
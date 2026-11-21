document.addEventListener('DOMContentLoaded', () => {
  const formCumple = document.getElementById('formCumple');
  if (!formCumple) return;

  const limiteAmigos = parseInt(formCumple.dataset.limiteAmigos || '0', 10);
  const iniMd = [
    parseInt(formCumple.dataset.iniMes || '1', 10),
    parseInt(formCumple.dataset.iniDia || '1', 10)
  ];
  const finMd = [
    parseInt(formCumple.dataset.finMes || '12', 10),
    parseInt(formCumple.dataset.finDia || '31', 10)
  ];

  const inputNombre = document.getElementById('nombre_completo');
  const inputFechaNac = document.getElementById('fecha_nacimiento');
  const selDia = document.getElementById('nac_dia');
  const selMes = document.getElementById('nac_mes');
  const selAnio = document.getElementById('nac_anio');
  const avisoRango = document.getElementById('avisoRangoFecha');
  const bloqueAmigos = document.getElementById('bloqueAmigos');
  const listaAmigos = document.getElementById('listaAmigos');
  const contadorAmigos = document.getElementById('contadorAmigos');
  const btnAgregarAmigo = document.getElementById('btnAgregarAmigo');

  function cmpTupla(a, b) {
    return a[0] !== b[0] ? a[0] - b[0] : a[1] - b[1];
  }

  function estaEnRango(dateStr) {
    if (!dateStr) return false;
    const partes = dateStr.split('-');
    if (partes.length !== 3) return false;
    const md = [parseInt(partes[1], 10), parseInt(partes[2], 10)];

    if (cmpTupla(iniMd, finMd) <= 0) {
      return cmpTupla(iniMd, md) <= 0 && cmpTupla(md, finMd) <= 0;
    }
    return cmpTupla(md, iniMd) >= 0 || cmpTupla(md, finMd) <= 0;
  }

  function actualizarContadorAmigos() {
    const actuales = listaAmigos.querySelectorAll('.amigo-row').length;
    const disponibles = Math.max(0, limiteAmigos - actuales);
    contadorAmigos.innerText = `Tenés disponible ${disponibles} ${disponibles === 1 ? 'amigo' : 'amigos'}`;
    if (btnAgregarAmigo) {
      btnAgregarAmigo.disabled = disponibles <= 0;
    }
  }

  function crearFilaAmigo() {
    const actuales = listaAmigos.querySelectorAll('.amigo-row').length;
    if (actuales >= limiteAmigos) return;

    const div = document.createElement('div');
    div.className = 'amigo-row row g-2 align-items-center';

    const colNombre = document.createElement('div');
    colNombre.className = 'col-md-6';
    const inputAmigoNombre = document.createElement('input');
    inputAmigoNombre.type = 'text';
    inputAmigoNombre.className = 'form-control form-control-sm uppercase-input';
    inputAmigoNombre.name = 'amigo_nombre[]';
    inputAmigoNombre.placeholder = 'Apellido y nombre del amigo';
    inputAmigoNombre.addEventListener('input', () => {
      inputAmigoNombre.value = inputAmigoNombre.value.toUpperCase();
    });
    colNombre.appendChild(inputAmigoNombre);

    const colDni = document.createElement('div');
    colDni.className = 'col-md-4';
    const inputAmigoDni = document.createElement('input');
    inputAmigoDni.type = 'text';
    inputAmigoDni.inputMode = 'numeric';
    inputAmigoDni.className = 'form-control form-control-sm';
    inputAmigoDni.name = 'amigo_dni[]';
    inputAmigoDni.placeholder = 'DNI';
    colDni.appendChild(inputAmigoDni);

    const colAccion = document.createElement('div');
    colAccion.className = 'col-md-2 text-end';
    const btnQuitar = document.createElement('button');
    btnQuitar.type = 'button';
    btnQuitar.className = 'btn btn-sm btn-outline-danger w-100';
    btnQuitar.innerText = 'Quitar';
    btnQuitar.addEventListener('click', () => {
      div.remove();
      actualizarContadorAmigos();
    });
    colAccion.appendChild(btnQuitar);

    div.appendChild(colNombre);
    div.appendChild(colDni);
    div.appendChild(colAccion);

    listaAmigos.appendChild(div);
    actualizarContadorAmigos();
  }

  function validarCumple() {
    if (!inputFechaNac || !bloqueAmigos) return;
    const val = inputFechaNac.value;

    if (!val) {
      bloqueAmigos.classList.add('d-none');
      avisoRango.innerText = '';
      return;
    }

    if (estaEnRango(val)) {
      avisoRango.className = 'form-text text-success mt-1';
      avisoRango.innerText = '✓ ¡Tu fecha de nacimiento está dentro del rango habilitado!';
      bloqueAmigos.classList.remove('d-none');
      if (listaAmigos.children.length === 0 && limiteAmigos > 0) {
        crearFilaAmigo();
      }
      actualizarContadorAmigos();
    } else {
      avisoRango.className = 'form-text text-danger mt-1';
      avisoRango.innerText = '✗ Tu fecha de nacimiento no entra en el rango de fechas de este beneficio.';
      bloqueAmigos.classList.add('d-none');
    }
  }

  function poblarSelectoresFecha() {
    if (!selDia || !selMes || !selAnio) return;

    const anioActual = new Date().getFullYear();
    const anioMax = anioActual - 14;
    const anioMin = anioActual - 85;

    for (let a = anioMax; a >= anioMin; a--) {
      const opt = document.createElement('option');
      opt.value = String(a);
      opt.textContent = String(a);
      selAnio.appendChild(opt);
    }

    for (let d = 1; d <= 31; d++) {
      const val = String(d).padStart(2, '0');
      const opt = document.createElement('option');
      opt.value = val;
      opt.textContent = String(d);
      selDia.appendChild(opt);
    }
  }

  function actualizarDiasDelMes() {
    if (!selDia || !selMes || !selAnio) return;

    const mes = parseInt(selMes.value || '0', 10);
    const anio = parseInt(selAnio.value || '2000', 10);
    const diaPrevio = selDia.value;
    const maxDias = mes ? new Date(anio, mes, 0).getDate() : 31;

    selDia.innerHTML = '<option value="" selected disabled>Día</option>';
    for (let d = 1; d <= maxDias; d++) {
      const val = String(d).padStart(2, '0');
      const opt = document.createElement('option');
      opt.value = val;
      opt.textContent = String(d);
      if (val === diaPrevio && d <= maxDias) {
        opt.selected = true;
      }
      selDia.appendChild(opt);
    }

    sincronizarFechaOculta();
  }

  function sincronizarFechaOculta() {
    if (!inputFechaNac) return;

    if (selDia && selMes && selAnio && selDia.value && selMes.value && selAnio.value) {
      inputFechaNac.value = `${selAnio.value}-${selMes.value}-${selDia.value}`;
    } else if (selDia && selMes && selAnio) {
      inputFechaNac.value = '';
    }

    validarCumple();
  }

  if (inputNombre) {
    inputNombre.addEventListener('input', () => {
      inputNombre.value = inputNombre.value.toUpperCase();
    });
  }

  if (selDia && selMes && selAnio) {
    poblarSelectoresFecha();
    selMes.addEventListener('change', actualizarDiasDelMes);
    selAnio.addEventListener('change', actualizarDiasDelMes);
    selDia.addEventListener('change', sincronizarFechaOculta);
  } else if (inputFechaNac) {
    inputFechaNac.addEventListener('change', validarCumple);
  }

  if (btnAgregarAmigo) {
    btnAgregarAmigo.addEventListener('click', crearFilaAmigo);
  }

  formCumple.addEventListener('submit', (e) => {
    formCumple.querySelectorAll('.uppercase-input').forEach((el) => {
      el.value = el.value.toUpperCase().trim();
    });

    if (selDia && selMes && selAnio && (!selDia.value || !selMes.value || !selAnio.value)) {
      e.preventDefault();
      avisoRango.className = 'form-text text-danger mt-1';
      avisoRango.innerText = '✗ Seleccioná día, mes y año de nacimiento.';
      return;
    }

    if (!estaEnRango(inputFechaNac.value)) {
      e.preventDefault();
      validarCumple();
    }
  });
});
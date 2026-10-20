let canvas = document.getElementById('canvasRuleta');
let ctx = canvas.getContext('2d');

let anguloActual = 0;
let girando = false;
let premioGanadoTexto = '';
let ultimoIndiceSonido = -1;

const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function reproducirSonidoTic() {
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(650, audioCtx.currentTime);
    gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.03);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.03);
}

function reproducirSonidoGanador() {
    if (audioCtx.state === 'suspended') audioCtx.resume();
    const notas = [523.25, 659.25, 783.99, 1046.50];
    notas.forEach((freq, i) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.2, audioCtx.currentTime + (i * 0.12));
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + (i * 0.12) + 0.4);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start(audioCtx.currentTime + (i * 0.12));
        osc.stop(audioCtx.currentTime + (i * 0.12) + 0.4);
    });
}

const colores = ['#111116', '#8a6d1c', '#721c24', '#0f5132', '#432874', '#b08d2b', '#1c1d22'];

window.onload = function() {
    const ultimaJugada = localStorage.getItem('ruleta_fecha_jugada');
    if (ultimaJugada) {
        const ahora = new Date().getTime();
        const diferenciaHoras = (ahora - parseInt(ultimaJugada)) / (1000 * 60 * 60);
        
        if (diferenciaHoras < 24) {
            document.getElementById('juego-section').innerHTML = `
                <div class="card card-casino p-3 text-center">
                    <h5 class="text-warning mb-2">⏳ ¡Ya participaste hoy!</h5>
                    <p class="text-muted small mb-0">Este celular ya giró la ruleta. Te esperamos en ANANA CLUB para canjear tu premio o volver a intentar mañana.</p>
                </div>
            `;
            return;
        }
    }
    dibujarRuleta();
};

function dibujarRuleta() {
    const totalPorciones = premios.length;
    const anguloPorcion = (2 * Math.PI) / totalPorciones;
    const centroX = canvas.width / 2;
    const centroY = canvas.height / 2;
    const radio = canvas.width / 2 - 10;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < totalPorciones; i++) {
        const anguloInicio = anguloActual + (i * anguloPorcion);
        const anguloFin = anguloInicio + anguloPorcion;

        ctx.beginPath();
        ctx.moveTo(centroX, centroY);
        ctx.arc(centroX, centroY, radio, anguloInicio, anguloFin);
        ctx.closePath();
        ctx.fillStyle = colores[i % colores.length];
        ctx.fill();
        ctx.lineWidth = 3;
        ctx.strokeStyle = '#d4af37';
        ctx.stroke();

        ctx.save();
        ctx.translate(centroX, centroY);
        ctx.rotate(anguloInicio + anguloPorcion / 2);
        ctx.textAlign = "right";
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 15px Montserrat";
        
        let texto = premios[i];
        if (texto.length > 18) texto = texto.substring(0, 16) + '...';
        
        ctx.fillText(texto, radio - 22, 5);
        ctx.restore();
    }

    ctx.beginPath();
    ctx.arc(centroX, centroY, 30, 0, 2 * Math.PI);
    ctx.fillStyle = '#08080c';
    ctx.fill();
    ctx.lineWidth = 3;
    ctx.strokeStyle = '#d4af37';
    ctx.stroke();
}

function iniciarGiro() {
    if (girando) return;
    girando = true;

    const btnGirar = document.getElementById('btnGirar');
    const joker = document.getElementById('joker');
    
    btnGirar.disabled = true;
    joker.classList.add('joker-spinning');

    fetch('/girar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            premioGanadoTexto = data.premio;
            const indiceGanador = premios.indexOf(data.premio);
            animarGiroRuleta(indiceGanador >= 0 ? indiceGanador : 0);
        } else {
            alert(data.error || 'Ocurrió un error.');
            btnGirar.disabled = false;
            joker.classList.remove('joker-spinning');
            girando = false;
        }
    })
    .catch(err => {
        console.error(err);
        alert('Error al conectar con el servidor.');
        btnGirar.disabled = false;
        joker.classList.remove('joker-spinning');
        girando = false;
    });
}

function animarGiroRuleta(indiceGanador) {
    const totalPorciones = premios.length;
    const anguloPorcion = (2 * Math.PI) / totalPorciones;
    const anguloObjetivoPorcion = (1.5 * Math.PI) - (indiceGanador * anguloPorcion) - (anguloPorcion / 2);
    
    const girosExtra = 6 * 2 * Math.PI;
    const anguloFinal = anguloActual + girosExtra + (anguloObjetivoPorcion - (anguloActual % (2 * Math.PI)));

    const duracion = 5000;
    const inicio = performance.now();

    function frame(tiempoActual) {
        const transcurrido = tiempoActual - inicio;
        const progreso = Math.min(transcurrido / duracion, 1);
        const easeOut = 1 - Math.pow(1 - progreso, 3.5);
        
        anguloActual = anguloActual + (anguloFinal - anguloActual) * (easeOut * 0.08);
        
        const porcionActualIndex = Math.floor((anguloActual % (2 * Math.PI)) / anguloPorcion);
        if (porcionActualIndex !== ultimoIndiceSonido) {
            reproducirSonidoTic();
            ultimoIndiceSonido = porcionActualIndex;
        }

        dibujarRuleta();

        if (progreso < 1) {
            requestAnimationFrame(frame);
        } else {
            document.getElementById('joker').classList.remove('joker-spinning');
            localStorage.setItem('ruleta_fecha_jugada', new Date().getTime().toString());
            
            reproducirSonidoGanador();
            confetti({
                particleCount: 100,
                spread: 70,
                origin: { y: 0.6 }
            });

            setTimeout(() => {
                document.getElementById('juego-section').classList.add('d-none');
                document.getElementById('textoPremioGanado').innerText = premioGanadoTexto;
                document.getElementById('premio-section').classList.remove('d-none');
            }, 600);
        }
    }
    requestAnimationFrame(frame);
}

function reclamarPremio() {
    const nombre = document.getElementById('nombre').value.trim();
    const telefono = document.getElementById('telefono').value.trim();

    if (!nombre || !telefono) {
        alert('Por favor ingresá tu nombre y teléfono para reclamar.');
        return;
    }

    fetch('/guardar_ganador', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre: nombre, telefono: telefono })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.href = '/reclamar';
        } else {
            alert(data.error || 'Error al guardar el premio.');
        }
    })
    .catch(err => {
        console.error(err);
        alert('Error de conexión.');
    });
}
// agent0range frontend anti-automation & anti-OCR hellscape

// Randomize DOM IDs and inject decoy elementsxport function hardenDOM() {
  // Randomize IDs
  document.querySelectorAll('[id]').forEach(el => {
    const newId = 'id_' + Math.random().toString(36).substr(2, 8);
    el.id = newId;
  });
  // Inject decoy fields
  for (let i = 0; i < 3; i++) {
    const decoy = document.createElement('input');
    decoy.type = 'text';
    decoy.style.position = 'absolute';
    decoy.style.left = `${Math.random() * 90}%`;
    decoy.style.top = `${Math.random() * 90}%`;
    decoy.style.opacity = '0.01';
    decoy.autocomplete = 'off';
    decoy.tabIndex = -1;
    decoy.ariaHidden = 'true';
    document.body.appendChild(decoy);
  }
}

// Animated noise overlay for anti-OCRxport function addNoiseOverlay() {
  const canvas = document.createElement('canvas');
  canvas.id = 'noise-overlay';
  canvas.style.position = 'fixed';
  canvas.style.top = '0';
  canvas.style.left = '0';
  canvas.style.width = '100vw';
  canvas.style.height = '100vh';
  canvas.style.pointerEvents = 'none';
  canvas.style.zIndex = '9999';
  document.body.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  function drawNoise() {
    const w = window.innerWidth, h = window.innerHeight;
    canvas.width = w; canvas.height = h;
    for (let y = 0; y < h; y += 2) {
      for (let x = 0; x < w; x += 2) {
        const shade = Math.floor(Math.random() * 255);
        ctx.fillStyle = `rgba(${shade},${shade},${shade},0.08)`;
        ctx.fillRect(x, y, 2, 2);
      }
    }
  }
  setInterval(drawNoise, 80);
}

// Dynamic watermark for anti-screenshot/anti-OCRxport function addWatermark(text: string) {
  const wm = document.createElement('div');
  wm.innerText = text;
  wm.style.position = 'fixed';
  wm.style.bottom = '2vh';
  wm.style.right = '2vw';
  wm.style.opacity = '0.15';
  wm.style.fontSize = '2.5vh';
  wm.style.fontFamily = 'monospace, sans-serif';
  wm.style.pointerEvents = 'none';
  wm.style.zIndex = '9998';
  wm.style.userSelect = 'none';
  document.body.appendChild(wm);
}

// Call these in your App.tsx or index.tsx on mount
// hardenDOM();
// addNoiseOverlay();
// addWatermark('agent0range // ultra secure');

const stage=document.getElementById('stage');
const slides=[...document.querySelectorAll('.slide')];
const label=document.getElementById('label'),count=document.getElementById('count'),bar=document.querySelector('#progress i');
let cur=0,demoTimer=null;

function fit(){const s=Math.min(innerWidth/1920,innerHeight/1080);stage.style.transform=`translate(-50%,-50%) scale(${s})`}
addEventListener('resize',fit);fit();

slides.forEach(sl=>sl.querySelectorAll('.r').forEach((el,i)=>el.style.setProperty('--i',i)));

const lines=[
  "You opened exercise 1. Shall we do it together?",
  "No worries. Look first: there's an x², so it's not linear. It's a parabola.",
  "Let me plot it. Solving the equation means finding where it crosses the axis.",
  "It crosses at two points. Compute Δ = b² − 4ac to find them. Your turn!",
  "Well done. I've prepared your revision sheet for this session."
];
function demo(on){
  const board=document.querySelector('.board'),items=[...document.querySelectorAll('.steps li')],say=document.querySelector('.say');
  clearInterval(demoTimer);let s=0;
  if(!board.querySelector('.sheet'))board.insertAdjacentHTML('beforeend','<div class="sheet"><p class="eyebrow"><b></b>Revision sheet</p><h4>Quadratics</h4><ul><li>x² → a parabola, not a line</li><li>Δ = b² − 4ac ; Δ &gt; 0 → two roots</li><li>x² − 5x + 6 = 0 → x = 2 or x = 3</li><li>To review: order of a and b</li></ul></div>');
  const set=i=>{board.dataset.s=i;items.forEach((li,k)=>li.classList.toggle('on',k===i));say.textContent=lines[i];say.classList.remove('swap');void say.offsetWidth;say.classList.add('swap')};
  if(!on){set(0);return}
  set(0);demoTimer=setInterval(()=>{s=(s+1)%lines.length;set(s)},3200);
  items.forEach((li,k)=>li.onclick=()=>{clearInterval(demoTimer);s=k;set(k)});
}

function go(n){
  cur=Math.max(0,Math.min(slides.length-1,n));
  slides.forEach((sl,i)=>sl.classList.toggle('active',i===cur));
  label.textContent=slides[cur].dataset.title;
  count.textContent=`${String(cur+1).padStart(2,'0')} / ${slides.length}`;
  bar.style.width=`${(cur+1)/slides.length*100}%`;
  history.replaceState(null,'',`#${cur+1}`);
  demo(slides[cur].classList.contains('demo'));
}
addEventListener('keydown',e=>{
  if(['ArrowRight','PageDown',' ','Enter'].includes(e.key)){e.preventDefault();go(cur+1)}
  if(['ArrowLeft','PageUp','Backspace'].includes(e.key)){e.preventDefault();go(cur-1)}
  if(e.key==='Home')go(0);if(e.key==='End')go(slides.length-1);
  if(e.key==='f')document.documentElement.requestFullscreen?.();
});
document.getElementById('next').onclick=()=>go(cur+1);
document.getElementById('prev').onclick=()=>go(cur-1);
let tx=null;addEventListener('touchstart',e=>tx=e.touches[0].clientX);addEventListener('touchend',e=>{if(tx===null)return;const d=e.changedTouches[0].clientX-tx;if(Math.abs(d)>50)go(cur+(d<0?1:-1));tx=null});
go((parseInt(location.hash.slice(1))||1)-1);

const stage=document.getElementById('stage');
const slides=[...document.querySelectorAll('.slide')];
const label=document.getElementById('label'),count=document.getElementById('count'),bar=document.querySelector('#progress i');
let cur=0,demoTimer=null;

function fit(){const s=Math.min(innerWidth/1920,innerHeight/1080);stage.style.transform=`translate(-50%,-50%) scale(${s})`}
addEventListener('resize',fit);fit();

slides.forEach(sl=>sl.querySelectorAll('.r').forEach((el,i)=>el.style.setProperty('--i',i)));

const lines=[
  "Tu as ouvert l'exercice 1. On le fait ensemble ?",
  "Pas de souci. Regarde d'abord : il y a un x², donc ce n'est pas affine. C'est une parabole.",
  "Je la trace. Résoudre l'équation, c'est trouver où elle coupe l'axe.",
  "Elle coupe en deux points. Calcule Δ = b² − 4ac pour les retrouver. À toi !",
  "Bravo. Je t'ai préparé la fiche de révision de la session."
];
function demo(on){
  const board=document.querySelector('.board'),items=[...document.querySelectorAll('.steps li')],say=document.querySelector('.say');
  clearInterval(demoTimer);let s=0;
  if(!board.querySelector('.sheet'))board.insertAdjacentHTML('beforeend','<div class="sheet"><p class="eyebrow"><b></b>Fiche de révision</p><h4>Second degré</h4><ul><li>x² → parabole, pas une droite</li><li>Δ = b² − 4ac ; Δ &gt; 0 → deux racines</li><li>x² − 5x + 6 = 0 → x = 2 ou x = 3</li><li>À revoir : ordre de a et b</li></ul></div>');
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

const stage=document.getElementById('stage');
const slides=[...document.querySelectorAll('.slide')];
const label=document.getElementById('label'),count=document.getElementById('count'),bar=document.querySelector('#progress i'),notes=document.getElementById('notes');
let cur=-1,timers=[];

function fit(){const s=Math.min(innerWidth/1920,innerHeight/1080);stage.style.transform=`translate(-50%,-50%) scale(${s})`}
addEventListener('resize',fit);fit();
slides.forEach(sl=>sl.querySelectorAll('.r').forEach((el,i)=>el.style.setProperty('--i',i)));
const later=(f,ms)=>timers.push(setTimeout(f,ms));
const every=(f,ms)=>timers.push(setInterval(f,ms));
const clear=()=>{timers.forEach(t=>{clearTimeout(t);clearInterval(t)});timers=[]};

// Slide 3: retyping the notebook into a chat box, with the usual fumbles.
const script=[["x^2 - 5x + 6 = 0",0],["\nD = b^2 - 4*a*c",0],["\ndelta",5],["Δ? how do I type delta",22],["\nD = 25 + 24",0]];
function typing(){
  const el=document.getElementById('typed');el.textContent='';let txt='',q=[];
  script.forEach(([s,back])=>{for(let i=0;i<back;i++)q.push(-1);for(const c of s)q.push(c)});
  let i=0;later(function step(){if(i>=q.length)return;const c=q[i++];txt=c===-1?txt.slice(0,-1):txt+c;el.textContent=txt.split('\n').slice(-2).join('\n');later(step,c===-1?40:c==='\n'?500:70)},1400);
}

// Slide 5: same board story as the landing hero.
function board(){
  const b=document.getElementById('board');let k=0;
  const set=()=>{b.querySelectorAll('[data-k]').forEach(e=>e.classList.toggle('on',k>=+e.dataset.k));
    b.querySelectorAll('[data-win]').forEach(e=>{const[a,z]=e.dataset.win.split('-').map(Number);e.classList.toggle('on',k>=a&&k<=z)});
    b.querySelector('.gcur').className='gcur'+(k>=4&&k<6?' at-err':k>=6?' at-end':'')};
  set();every(()=>{k=(k+1)%10;set()},1500);
}

function clips(sl,on){
  sl.querySelectorAll('.clip video').forEach(v=>{
    if(!on){v.pause();return}
    v.currentTime=0;v.muted=false;v.play().catch(()=>{v.muted=true;v.play().catch(()=>{})});
  });
}
document.querySelectorAll('.clip').forEach(f=>{
  const v=f.querySelector('video');
  v.addEventListener('loadeddata',()=>f.classList.add('ready'));
  v.addEventListener('click',()=>v.paused?v.play():v.pause());
  v.src=f.dataset.clip;
});

function go(n){
  n=Math.max(0,Math.min(slides.length-1,n));if(n===cur)return;
  if(cur>=0)clips(slides[cur],false);
  cur=n;clear();
  slides.forEach((sl,i)=>sl.classList.toggle('active',i===cur));
  const sl=slides[cur];
  label.textContent=sl.dataset.title;
  count.textContent=`${String(cur+1).padStart(2,'0')} / ${slides.length}`;
  bar.style.width=`${(cur+1)/slides.length*100}%`;
  notes.textContent=sl.querySelector('.notes')?.textContent||'';
  history.replaceState(null,'',`#${cur+1}`);
  if(sl.classList.contains('pain'))typing();
  if(sl.querySelector('#board'))board();
  clips(sl,true);
}
addEventListener('keydown',e=>{
  if(['ArrowRight','PageDown',' ','Enter'].includes(e.key)){e.preventDefault();go(cur+1)}
  if(['ArrowLeft','PageUp','Backspace'].includes(e.key)){e.preventDefault();go(cur-1)}
  if(e.key==='Home')go(0);if(e.key==='End')go(slides.length-1);
  if(e.key==='f')document.documentElement.requestFullscreen?.();
  if(e.key==='n')document.body.classList.toggle('show-notes');
  if(e.key==='m')slides[cur].querySelectorAll('video').forEach(v=>v.muted=!v.muted);
});
document.getElementById('next').onclick=()=>go(cur+1);
document.getElementById('prev').onclick=()=>go(cur-1);
let tx=null;addEventListener('touchstart',e=>tx=e.touches[0].clientX);addEventListener('touchend',e=>{if(tx===null)return;const d=e.changedTouches[0].clientX-tx;if(Math.abs(d)>50)go(cur+(d<0?1:-1));tx=null});
go((parseInt(location.hash.slice(1))||1)-1);

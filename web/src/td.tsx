import React, {useEffect, useMemo, useRef, useState} from "react";
import {createRoot} from "react-dom/client";
import katex from "katex";
import "katex/dist/katex.min.css";
import "./style.css";
import "./board.css";
import {getBridge} from "./bridge";
import {Orb} from "./orb";
import {Reveal} from "./reveal";
import {annotationLeader, annotationSize, arrowEndpoints, createCursorMotion, cursorRestBeside, intentColor, placeAnnotation, pointsToPath, seedFrom, sketchArrow, sketchEllipsePoints, type AnnotationRect, type CursorMotion, type CursorPoint, type CursorVisual} from "./annotations";
import {mountNotch} from "./notch";
import * as pdfjs from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import {loadWebDocument, type WebDocument} from "./webbridge";

const bridge = getBridge();
pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;
const exercises = [
  {id:"exercice-1", title:"Exercice 1", lines:["Résous dans ℝ : x² − 5x + 6 = 0"], math:"x^2 - 5x + 6 = 0", instruction:"Résous l’équation et vérifie tes solutions."},
  {id:"exercice-2", title:"Exercice 2", lines:["Résous dans ℝ : 2x² + 3x − 2 = 0"], math:"2x^2 + 3x - 2 = 0", instruction:"Résous l’équation et vérifie tes solutions."},
  {id:"exercice-3", title:"Exercice 3", lines:["Écris sous forme canonique : x² − 4x + 1"], math:"x^2 - 4x + 1", instruction:"Écris l’expression sous forme canonique."},
  {id:"exercice-4", title:"Exercice 4", lines:["Étudie le signe de −x² + x + 6"], math:"-x^2 + x + 6", instruction:"Dresse le tableau de signes."},
];
type Rect = {x:number;y:number;w:number;h:number};
type ViewElement = {id:number;text:string;rect:Rect};
type PaintElement = ViewElement & {active:boolean;selected:boolean;checked?:boolean;isColor:boolean;isLayer:boolean;tag:string;value:string;in_dialog:boolean;dialog?:string};
type PendingRealtimeResponse = {turn:number;response?:Record<string,unknown>};
type ViewApi = {elements:()=>ViewElement[];exec:(name:string,args:Record<string,any>)=>Promise<Record<string,any>>;close?:()=>void;waitForAnimations:()=>Promise<void>};
type BoardApi = ViewApi & {snapshot:()=>string};
type GeraldVoiceState = {turn:number;settledTurn:number;pendingTools:number;settledAt:number;responsesCreated:number;responsesDone:number};
declare global { interface Window { geraldTD?:ViewApi; geraldBoard?:BoardApi; __geraldLog?:Record<string,unknown>[]; __geraldState?:GeraldVoiceState } }
const params = new URLSearchParams(location.search);
const voiceMode = params.get("voice") === "1";
const liveMode = params.get("live") === "1";
const docId = params.has("doc") ? Number(params.get("doc")) : null;
const docMode = docId !== null && Number.isFinite(docId);
const boardMode = params.get("board") === "1";
const embedded = params.get("embed") === "1";
const paintMode = params.get("app") === "paint";
function boundsOfPoints(points:CursorPoint[],padding=0):AnnotationRect {
  const xs=points.map(({x})=>x),ys=points.map(({y})=>y),left=Math.min(...xs),top=Math.min(...ys);
  return {x:left-padding,y:top-padding,w:Math.max(...xs)-left+padding*2,h:Math.max(...ys)-top+padding*2};
}
function unionBounds(...rects:AnnotationRect[]):AnnotationRect {
  const left=Math.min(...rects.map(rect=>rect.x)),top=Math.min(...rects.map(rect=>rect.y));
  const right=Math.max(...rects.map(rect=>rect.x+rect.w)),bottom=Math.max(...rects.map(rect=>rect.y+rect.h));
  return {x:left,y:top,w:right-left,h:bottom-top};
}
function pointsLength(points:CursorPoint[]):number {
  return points.reduce((length,point,index)=>index?length+Math.hypot(point.x-points[index-1].x,point.y-points[index-1].y):0,0);
}
function moveToRest(queue:CursorMotion,to:CursorPoint):Promise<void> {
  const current=queue.current();
  return Math.hypot(to.x-current.x,to.y-current.y)<4?Promise.resolve():queue.moveTo(to);
}
function animateHeadProgress(onProgress:(progress:number)=>void):Promise<void> {
  if(window.matchMedia("(prefers-reduced-motion: reduce)").matches){onProgress(1);return Promise.resolve();}
  const start=performance.now();
  return new Promise(resolve=>{const frame=(now:number)=>{const progress=Math.min(1,(now-start)/180);onProgress(progress);if(progress<1)requestAnimationFrame(frame);else resolve();};requestAnimationFrame(frame);});
}
type PdfLine = {id:number; text:string; x:number; y:number; w:number; h:number; fontSize:number};
function PdfPage({pdf, pageNumber}: {pdf: pdfjs.PDFDocumentProxy; pageNumber: number}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [lines, setLines] = useState<PdfLine[]>([]);
  const [pageSize, setPageSize] = useState({width: 0, height: 0});
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const page = await pdf.getPage(pageNumber);
      const base = page.getViewport({scale: 1});
      const scale = Math.min(1.5, Math.max(0.5, (window.innerWidth - 48) / base.width));
      const viewport = page.getViewport({scale});
      const target = canvas.current;
      if (!target || cancelled) return;
      target.width = Math.ceil(viewport.width);
      target.height = Math.ceil(viewport.height);
      setPageSize({width: viewport.width, height: viewport.height});
      const canvasContext = target.getContext("2d");
      if (!canvasContext) return;
      await page.render({canvasContext, viewport}).promise;
      const content = await page.getTextContent();
      const grouped: Array<{top: number; items: Array<{x: number; width: number; height: number; text: string}>}> = [];
      for (const item of content.items) {
        if (!("str" in item) || !item.str.trim()) continue;
        const transform = pdfjs.Util.transform(viewport.transform, item.transform);
        const height = Math.max(8, Math.hypot(transform[2], transform[3]));
        const top = transform[5] - height;
        let line = grouped.find(candidate => Math.abs(candidate.top - top) < height * 0.45);
        if (!line) {
          line = {top, items: []};
          grouped.push(line);
        }
        line.items.push({x: transform[4], width: item.width * scale, height, text: item.str});
      }
      if (cancelled) return;
      setLines(grouped.map((line, index) => {
        const items = line.items.sort((a, b) => a.x - b.x);
        const left = Math.min(...items.map(item => item.x));
        const right = Math.max(...items.map(item => item.x + item.width));
        const text = items.reduce((value, item, itemIndex) => {
          if (!itemIndex) return item.text;
          const previous = items[itemIndex - 1];
          return value + (item.x - previous.x - previous.width > item.height * 0.16 ? " " : "") + item.text;
        }, "");
        const height = Math.max(...items.map(item => item.height));
        return {id: 1000 + pageNumber * 100 + index, text, x: left, y: line.top, w: right - left, h: height, fontSize: height};
      }));
    })();
    return () => { cancelled = true; };
  }, [pdf, pageNumber]);
  return <div className="doc-pdf-page" style={{width: pageSize.width || undefined, height: pageSize.height || undefined}}>
    <canvas ref={canvas}/>
    <div className="doc-pdf-text">{lines.map(line=><span
      key={line.id}
      data-gerald-id={line.id}
      style={{left: line.x, top: line.y, width: line.w, height: line.h, fontSize: line.fontSize}}
    >{line.text}</span>)}</div>
  </div>;
}

function PdfDocument({file}: {file: WebDocument}) {
  const [pdf, setPdf] = useState<pdfjs.PDFDocumentProxy | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    let loaded: pdfjs.PDFDocumentProxy | null = null;
    if (!file.blob) return;
    void file.blob.arrayBuffer().then(data => pdfjs.getDocument({data}).promise).then(document => {
      loaded = document;
      if (!cancelled) setPdf(document);
      else void document.destroy();
    }).catch(() => { if (!cancelled) setError("Impossible d’ouvrir ce PDF."); });
    return () => { cancelled = true; if (loaded) void loaded.destroy(); };
  }, [file]);
  if (error) return <p role="alert">{error}</p>;
  if (!pdf) return <p className="doc-loading">Chargement du PDF…</p>;
  return <div className="doc-pdf-scroll">{Array.from({length: pdf.numPages}, (_, index)=><PdfPage key={index} pdf={pdf} pageNumber={index + 1}/>)}</div>;
}

function MarkdownDocument({content}: {content: string}) {
  const paragraphs = content.split(/\n\s*\n/).map(value => value.trim()).filter(Boolean);
  return <article className="doc-markdown">
    {paragraphs.map((paragraph, index) => {
      const text = paragraph.replace(/^#{1,6}\s*/, "").replace(/^[-*]\s*/, "").replace(/`([^`]+)`/g, "$1");
      const html = text.split(/(\\\([^)]*\\\)|\$[^$]+\$)/g).map(part => {
        const math = part.startsWith("\\(") ? part.slice(2, -2) : part.startsWith("$") ? part.slice(1, -1) : null;
        return math === null ? part : katex.renderToString(math, {throwOnError: false, output: "htmlAndMathml"});
      }).join("");
      return <p data-gerald-id={2000 + index} key={index} dangerouslySetInnerHTML={{__html: html}}/>;
    })}
  </article>;
}

function DocumentView({file}: {file: WebDocument}) {
  const imageUrl = useMemo(() => file.blob ? URL.createObjectURL(file.blob) : "", [file]);
  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl); }, [imageUrl]);
  if (file.mime === "application/pdf") return <PdfDocument file={file}/>;
  if (file.mime.startsWith("image/")) return <div className="doc-image-scroll"><img data-gerald-id="3000" src={imageUrl} alt={file.filename}/></div>;
  return <MarkdownDocument content={file.content ?? ""}/>;
}
const textPattern = (value:string) => new RegExp([...value.trim()].map(char => {
  const escaped=char.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");
  return /\s/.test(char)?"\\s+":/[()[\]{}.,:+−\-\/]/.test(char)?`\\s*${escaped}\\s*`:escaped;
}).join(""),"i");
const voiceState = () => window.__geraldState ??= {turn:0,settledTurn:0,pendingTools:0,settledAt:0,responsesCreated:0,responsesDone:0};
const voiceLog = () => window.__geraldLog ??= [];

function targetRect(args:Record<string,any>):Rect|null {
  const elements = [...document.querySelectorAll<HTMLElement>("[data-gerald-id]")];
  let element = elements.find(e => e.dataset.geraldId === String(args.element_id));
  if (!element && typeof args.target_text === "string") {
    const pattern=textPattern(args.target_text);
    element = elements.find(e => pattern.test(e.innerText));
  }
  if (!element) return null;
  let rect = element.getBoundingClientRect();
  if (typeof args.target_text === "string" && args.target_text) {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    const nodes:Text[]=[]; let node:Node|null;
    while ((node=walker.nextNode())) if (!node.parentElement?.closest(".katex-mathml,[aria-hidden=true]")) nodes.push(node as Text);
    const raw = nodes.map(n=>n.data).join("");
    const match=textPattern(args.target_text).exec(raw);
    if(!match)return null;
    if (match) {
      const locate=(offset:number,end:boolean)=>{let base=0;for(const n of nodes){const next=base+n.length;if(offset<next||end&&offset===next)return [n,Math.max(0,Math.min(n.length,offset-base))] as const;base=next;}const last=nodes[nodes.length-1];return [last,last.length] as const;};
      if(nodes.length){const [start,so]=locate(match.index,false),[finish,fo]=locate(match.index+match[0].length,true);const range=document.createRange();range.setStart(start,so);range.setEnd(finish,fo);rect=range.getBoundingClientRect();}
    }
  }
  return {x:rect.x,y:rect.y,w:rect.width,h:rect.height};
}

function TD(){
  const boardParams = new URLSearchParams({
    voice: "1",
    title: params.get("title") ?? "",
    lines: params.get("lines") ?? "[]",
  });
  const initialBoardSrc = liveMode
    ? "/board.html?voice=1&live=1"
    : boardMode ? `/board.html?${boardParams}` : "";
  const [question,setQuestion]=useState(""),[status,setStatus]=useState("idle"),[caption,setCaption]=useState(""),[captionFading,setCaptionFading]=useState(false),[connecting,setConnecting]=useState(false),[audioLevel,setAudioLevel]=useState(0),[voiceError,setVoiceError]=useState(""),[micEnabled,setMicEnabled]=useState(false);
  const [boardOpen,setBoardOpen]=useState(liveMode||boardMode),[boardSrc,setBoardSrc]=useState(initialBoardSrc);
  const [docFile,setDocFile]=useState<WebDocument|null>(null);
  const [activeExercise,setActiveExercise]=useState(exercises[0]);
  const [marks,setMarks]=useState<Array<{id:string;kind:string;rect:Rect;text?:string;to?:Rect;annotationTarget?:Rect;leader?:boolean;color?:string|null;fill?:string|null;progress?:number;head?:number;points?:CursorPoint[];ghostPoints?:CursorPoint[];shaftPoints?:CursorPoint[];headPoints?:[CursorPoint,CursorPoint,CursorPoint]}>>([]);
  const cursorRest={x:innerWidth/2,y:innerHeight-90};
  const [cursor,setCursor]=useState<CursorVisual>({...cursorRest,visible:false});
  const cursorMotion=useRef<ReturnType<typeof createCursorMotion>|null>(null);
  if(!cursorMotion.current)cursorMotion.current=createCursorMotion(cursorRest,setCursor);
  const pendingAnnotations=useRef(new Map<string,Rect>());
  const [answer,setAnswer]=useState<{q:string;text:string;ex:typeof exercises[number]}|null>(null);
  const [suggestion,setSuggestion]=useState(false);
  const boardOpenRef=useRef(liveMode||boardMode);
  const frame=useRef<HTMLIFrameElement>(null), paintFrame=useRef<HTMLIFrameElement>(null), audio=useRef<HTMLAudioElement>(null);
  const paintIds=useRef(new WeakMap<Element,number>()), nextPaintId=useRef(7000);
  const peer=useRef<RTCPeerConnection|null>(null), channel=useRef<RTCDataChannel|null>(null), stream=useRef<MediaStream|null>(null);
  const audioContext=useRef<AudioContext|null>(null), micAnalyser=useRef<AnalyserNode|null>(null), remoteAnalyser=useRef<AnalyserNode|null>(null);
  const pushToTalk=useRef(false), toggleMic=useRef(false), pttPreviousMic=useRef(false);
  const captionTimer=useRef<number|null>(null), handled=useRef(new Set<string>());
  const sessionReady=useRef(false);
  const activeResponse=useRef<string|null>(null), activeResponseTurn=useRef<number|null>(null);
  const responseStartPending=useRef(false), pendingResponseTurn=useRef<number|null>(null);
  const responseTurns=useRef(new Map<string,number>()), completedResponses=useRef(new Set<string>());
  const processingTools=useRef(false), dispatchingResponse=useRef(false);
  const queuedTurns=useRef<Array<{turn:number;text:string}>>([]);
  const pendingResponses=useRef<PendingRealtimeResponse[]>([]);
  const responseTurn=useRef(0);
  useEffect(()=>{
    if(!docMode||docId===null)return;
    let active=true;
    void loadWebDocument(docId).then(file=>{if(active)setDocFile(file);}).catch(error=>console.error("Document load failed",error));
    return()=>{active=false;};
  },[]);
  const attachAnalyser=(media:MediaStream,kind:"mic"|"remote")=>{
    const context=audioContext.current??new AudioContext();audioContext.current=context;
    const analyser=context.createAnalyser();analyser.fftSize=512;
    context.createMediaStreamSource(media).connect(analyser);
    if(kind==="mic")micAnalyser.current=analyser;else remoteAnalyser.current=analyser;
  };
  const openBoard=(id?:string)=>{
    if(paintMode)return;
    if(docMode){
      setBoardSrc("/board.html?voice=1&live=1");
      boardOpenRef.current=true;
      setBoardOpen(true);
      return;
    }
    const ex=exercises.find(item=>item.id===id)??exercises[0]; setActiveExercise(ex);
    const query=new URLSearchParams({title:ex.title,lines:JSON.stringify(ex.lines),voice:"1"});
    setBoardSrc(`/board.html?${query}`); boardOpenRef.current=true; setBoardOpen(true);
    if(embedded)window.parent.postMessage({type:"gerald-last-exercise",title:ex.title,lines:ex.lines},location.origin);
  };
  const paintElements=():PaintElement[]=>{
    const iframe=paintFrame.current,doc=iframe?.contentDocument;
    if(!iframe||!doc)return [];
    const frameRect=iframe.getBoundingClientRect();
    const scaleX=frameRect.width/Math.max(1,iframe.clientWidth),scaleY=frameRect.height/Math.max(1,iframe.clientHeight);
    const visible=(element:HTMLElement)=>{
      const rect=element.getBoundingClientRect(),style=doc.defaultView?.getComputedStyle(element);
      return Boolean(rect.width&&rect.height&&style?.display!=="none"&&style?.visibility!=="hidden"&&Number(style?.opacity)!==0);
    };
    const nodes=[...doc.querySelectorAll<HTMLElement>("*")].filter(visible);
    const hasDataClickTarget=(element:HTMLElement)=>[...element.attributes].some(attribute=>{
      const name=attribute.name.toLowerCase(),value=attribute.value.trim();
      return Boolean(value&&(/^data-(?:key|action|click|target|tool|command|layer-id)$/.test(name)
        ||(name==="data-id"&&/(?:^|[_-])(?:button|item|tool|action|toggle)$/i.test(value))));
    });
    const clickable=new Set(nodes.filter(element=>{
      const style=doc.defaultView?.getComputedStyle(element);
      return style?.cursor==="pointer"||typeof element.onclick==="function"||hasDataClickTarget(element);
    }));
    const hasClickableAncestor=(element:HTMLElement)=>{
      let parent=element.parentElement;
      while(parent){
        if(clickable.has(parent))return true;
        parent=parent.parentElement;
      }
      return false;
    };
    const dialogs=nodes.filter(element=>element.matches("[role='dialog'],dialog,.popup,.modal,[aria-modal='true']"));
    const dialogTitle=(element:HTMLElement)=>{
      const title=element.querySelector<HTMLElement>("[data-id='popup_title'],h1,h2,h3");
      return title?.innerText.trim()||element.getAttribute("aria-label")?.trim()||"Dialog";
    };
    const candidates=nodes.filter(element=>{
      const semantic=element.matches("button,a,input,select,[role='button'],[role='menuitem'],[title],[class*='layer']");
      return (semantic||clickable.has(element))&&!hasClickableAncestor(element);
    });
    return candidates.map((element,index)=>{
      const rect=element.getBoundingClientRect();
      let id=paintIds.current.get(element);
      if(!id){id=nextPaintId.current++;paintIds.current.set(element,id);element.dataset.geraldId=String(id);}
      const className=element.getAttribute("class")??"";
      const active=/active/i.test(className)||element.getAttribute("aria-pressed")==="true";
      const selected=/selected/i.test(className)||element.getAttribute("aria-selected")==="true";
      const input=element.tagName==="INPUT"?element as HTMLInputElement:null;
      const select=element.tagName==="SELECT"?element as HTMLSelectElement:null;
      const image=element.tagName==="IMG"?element as HTMLImageElement:element.querySelector<HTMLImageElement>("img");
      const inputValue=input?.value.trim()??select?.value.trim()??"";
      const inputContainer=input?.closest<HTMLElement>(".item,.row");
      const inputLabelRaw=[...(input?.labels??[])].map(label=>label.innerText.trim()).find(Boolean)
        ||inputContainer?.querySelector<HTMLElement>("label,.label")?.innerText.trim()
        ||(input?.id==="color_hex"?"Hex":input?.getAttribute("aria-label")||input?.title||input?.placeholder||input?.id.replaceAll("_"," ")||"");
      const inputLabel=inputLabelRaw.replace(/[:：]\s*$/,"");
      const inputText=input?(inputValue?`${inputLabel?`${inputLabel} `:""}${inputValue}`:inputLabel):inputValue;
      const checkbox=Boolean(input?.type==="checkbox"||element.getAttribute("role")==="checkbox"
        ||element.hasAttribute("aria-checked")||element.hasAttribute("aria-pressed"));
      const checked=input?.type==="checkbox"?input.checked
        :element.getAttribute("aria-checked")==="true"||element.getAttribute("aria-pressed")==="true";
      const baseText=(element.innerText?.trim()
        ||image?.alt.trim()||image?.title.trim()
        ||element.getAttribute("title")?.trim()||element.getAttribute("aria-label")?.trim()
        ||inputText
        ||element.parentElement?.innerText?.trim()||"").trim();
      const text=`${baseText}${checkbox?(checked?" ✓":" ✗"):""}`.trim();
      const containingDialog=dialogs.filter(dialog=>dialog.contains(element)).pop();
      return {order:index,item:{
        id,text,active,selected,checked:checkbox?checked:undefined,isColor:input?.type==="color"||input?.id==="color_hex",
        isLayer:/layers_list|layer-row|layer_row/i.test(className)||element.hasAttribute("data-layer-id"),
        tag:element.tagName.toLowerCase(),value:inputValue,
        in_dialog:Boolean(containingDialog),dialog:containingDialog?dialogTitle(containingDialog):undefined,
        rect:{x:frameRect.x+rect.x*scaleX,y:frameRect.y+rect.y*scaleY,w:rect.width*scaleX,h:rect.height*scaleY},
      }};
    }).sort((a,b)=>Number(b.item.in_dialog)-Number(a.item.in_dialog)
      ||Number(b.item.active||b.item.selected)-Number(a.item.active||a.item.selected)
      ||a.order-b.order).slice(0,150).map(entry=>entry.item);
  };
  const paintTargetRect=(args:Record<string,any>):Rect|null=>{
    const elements=paintElements();
    const element=elements.find(item=>item.id===Number(args.element_id))
      ??(typeof args.target_text==="string"?elements.find(item=>textPattern(args.target_text).test(item.text)):undefined);
    return element?.rect??null;
  };
  const elements=():ViewElement[]=>paintMode?paintElements():[...document.querySelectorAll<HTMLElement>("[data-gerald-id]")].filter(e=>e.getClientRects().length).map(e=>{const r=e.getBoundingClientRect();return {id:Number(e.dataset.geraldId),text:(e instanceof HTMLInputElement?e.value||e.placeholder:e.innerText||"").trim(),rect:{x:r.x,y:r.y,w:r.width,h:r.height}};});
  const annotationOccupants=(target?:AnnotationRect,extra:AnnotationRect[]=[]):AnnotationRect[]=>[
      ...elements().map(element=>element.rect),
      ...marks.filter(mark=>mark.kind==="note"||mark.kind==="tip").map(mark=>mark.rect),
      ...pendingAnnotations.current.values(),
      ...(target?[target]:[]),...extra,
    ];
  const viewport=()=>({w:innerWidth,h:innerHeight});
  const placeBeside=(target:Rect,text:string,kind:"note"|"tip")=>
    placeAnnotation(target,annotationSize(text,kind),annotationOccupants(target),viewport());
  const restBeside=(bounds:AnnotationRect,extra:AnnotationRect[]=[])=>
    cursorRestBeside(bounds,annotationOccupants(bounds,extra),viewport());
  const waitForPaint=()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve())));
  const addMark=(mark:typeof marks[number])=>setMarks(items=>[...items,mark]);
  const updateMarkProgress=(id:string,progress:number)=>setMarks(items=>items.map(mark=>mark.id===id?{...mark,progress}:mark));
  const updateMarkHead=(id:string,head:number)=>setMarks(items=>items.map(mark=>mark.id===id?{...mark,head}:mark));
  const exec=async(name:string,args:Record<string,any>)=>{
    if(name==="open_board"){if(paintMode)return {ok:false,error:"open_board is unavailable in paint mode"};openBoard(docMode?undefined:String(args.exercise_id));return {ok:true};}
    const motion=cursorMotion.current!;
    if(name==="clear_gerald"){
      pendingAnnotations.current.clear();
      motion.enqueue(()=>{setMarks([]);motion.clear();});
      return {ok:true};
    }
    const color=intentColor(args.intent);
    const highlightFill=intentColor(args.intent,null,0.16);
    const resolveTarget=(target:Record<string,any>)=>paintMode?paintTargetRect(target):targetRect(target);
    const from=name==="arrow"?resolveTarget(args.from??{}):resolveTarget(args);
    const to=name==="arrow"?resolveTarget(args.to??{}):null;
    if(name==="arrow"&&(!from||!to))return {ok:false,error:"arrow targets were not found"};
    const endpoints=name==="arrow"&&from&&to?arrowEndpoints(from,to):null;
    if(name==="arrow"&&!endpoints)return {ok:false,error:"arrow endpoints could not be calculated"};
    const r=from??(typeof args.target_text!=="string"&&typeof args.x==="number"&&typeof args.y==="number"?{x:args.x,y:args.y,w:Number(args.w)||120,h:Number(args.h)||38}:null);
    if(name==="tip"){
      if(typeof args.text!=="string")return {ok:false,error:"tip requires text"};
      const pos=r??{x:innerWidth/2,y:innerHeight-130,w:0,h:0};
      const placement=placeBeside(pos,args.text,"tip");
      if(!placement)return {ok:false,error:"no free space to place the tip beside its target"};
      const id=crypto.randomUUID();
      pendingAnnotations.current.set(id,placement.rect);
      motion.enqueue(async queue=>{
        await queue.moveTo({x:pos.x+pos.w/2,y:pos.y+pos.h/2});
        addMark({id,kind:"tip",rect:placement.rect,text:args.text,color,annotationTarget:r?pos:undefined,leader:r?placement.leader:false});
        await waitForPaint();
        pendingAnnotations.current.delete(id);
        await moveToRest(queue,restBeside(unionBounds(pos,placement.rect),[pos,placement.rect]));
      });
      return {ok:true,target:pos,annotation:placement.rect};
    }
    if(name==="write"||name==="write_math"){
      const pos=r??{x:Number(args.x)||120,y:Number(args.y)||160,w:0,h:0};
      const id=crypto.randomUUID();
      motion.enqueue(async queue=>{
        await queue.moveTo({x:pos.x,y:pos.y});
        addMark({id,kind:"write",rect:pos,text:String(args.text??args.latex??""),color:color??"#111"});
        const text=String(args.text??args.latex??""),size=Number(args.size)||32;
        await moveToRest(queue,restBeside({x:pos.x,y:pos.y-size,w:Math.max(size,text.length*size*.65),h:size*1.25}));
      });
      return {ok:true};
    }
    if(!r)return {ok:false,error:"target not found"};
    if(!["circle","underline","point","highlight","arrow","note"].includes(name))return {ok:false,error:`unknown TD tool: ${name}`};
    const text=String(args.text??args.label??"");
    if(name==="note"){
      const placement=placeBeside(r,text,"note");
      if(!placement)return {ok:false,error:"no free space to place the note beside its target"};
      const id=crypto.randomUUID();
      pendingAnnotations.current.set(id,placement.rect);
      motion.enqueue(async queue=>{
        await queue.moveTo({x:r.x+r.w/2,y:r.y+r.h/2});
        addMark({id,kind:"note",rect:placement.rect,text,color,annotationTarget:r,leader:placement.leader});
        await waitForPaint();
        pendingAnnotations.current.delete(id);
        await moveToRest(queue,restBeside(unionBounds(r,placement.rect),[r,placement.rect]));
      });
      return {ok:true,target:r,annotation:placement.rect};
    }
    const exactText=typeof args.target_text==="string"&&args.target_text.length>0;
    const rect={x:r.x+r.w/2,y:r.y+r.h/2,w:exactText?r.w:Number(args.w)||r.w,h:exactText?r.h:Number(args.h)||r.h};
    if(name==="arrow"&&endpoints){
      const {x1,y1,x2,y2}=endpoints;
      const id=crypto.randomUUID();
      const {shaft,head}=sketchArrow(x1,y1,x2,y2,seedFrom(id));
      const bounds=boundsOfPoints([...shaft,...head],2);
      motion.enqueue(async queue=>{
        await queue.moveTo(shaft[0]);
        addMark({id,kind:"arrow",rect:{x:x1,y:y1,w:x2-x1,h:y2-y1},text,to:{x:x2,y:y2,w:0,h:0},color,progress:0,head:0,shaftPoints:shaft,headPoints:head});
        await waitForPaint();
        await queue.moveAlong(shaft,Math.max(380,Math.min(800,pointsLength(shaft)*2.5)),progress=>updateMarkProgress(id,progress));
        await animateHeadProgress(progress=>updateMarkHead(id,progress));
        await moveToRest(queue,restBeside(bounds));
      });
      return {ok:true,target:{x:x2,y:y2},from:{x:x1,y:y1},to:{x:x2,y:y2}};
    }
    const id=crypto.randomUUID();
    const mark={id,kind:name,rect,text,color,fill:name==="highlight"?highlightFill:null};
    if(name==="underline"||name==="highlight"){
      const start={x:rect.x-rect.w/2,y:rect.y+rect.h/2};
      const end={x:rect.x+rect.w/2,y:rect.y+rect.h/2};
      motion.enqueue(async queue=>{
        await queue.moveTo(start);
        addMark({...mark,progress:0});
        await waitForPaint();
        await queue.moveTo(end,progress=>updateMarkProgress(id,progress));
        const bounds=name==="underline"?{x:rect.x-rect.w/2,y:rect.y+rect.h/2-2,w:rect.w,h:4}:{x:rect.x-rect.w/2,y:rect.y-rect.h/2,w:rect.w,h:rect.h};
        await moveToRest(queue,restBeside(bounds));
      });
    }else if(name==="circle"){
      const points=sketchEllipsePoints(rect.x,rect.y,rect.w/2,rect.h/2,seedFrom(id));
      const ghostPoints=sketchEllipsePoints(rect.x,rect.y,rect.w/2,rect.h/2,seedFrom(id)+.37);
      const bounds=boundsOfPoints([...points,...ghostPoints],2);
      motion.enqueue(async queue=>{
        await queue.moveTo(points[0]);
        addMark({...mark,progress:0,points,ghostPoints});
        await waitForPaint();
        await queue.moveAlong(points,Math.max(650,Math.min(1100,pointsLength(points)*2.2)),progress=>updateMarkProgress(id,progress));
        await moveToRest(queue,restBeside(bounds));
      });
    }else{
      const bounds=name==="point"?{x:rect.x-5,y:rect.y-5,w:10,h:10}:rect;
      motion.enqueue(async queue=>{
        await queue.moveTo({x:rect.x,y:rect.y});
        addMark({...mark,progress:1});
        await moveToRest(queue,restBeside(bounds));
      });
    }
    return {ok:true,target:{x:rect.x,y:rect.y}};
  };
  useEffect(()=>{window.geraldTD={elements,exec,close:()=>{boardOpenRef.current=false;setBoardOpen(false);},waitForAnimations:()=>cursorMotion.current!.waitForAnimations()};return()=>{delete window.geraldTD;};});
  const getBoardApi=async()=>{for(let i=0;i<100;i++){const api=frame.current?.contentWindow?.geraldBoard;if(api)return api;await new Promise(resolve=>setTimeout(resolve,20));}return null;};
  const sendEvent=(event:Record<string,unknown>)=>{if(channel.current?.readyState!=="open")return false;channel.current.send(JSON.stringify(event));return true;};
  const documentImage=async()=>{
    if(!docMode||!docFile)return undefined;
    let source:HTMLCanvasElement|HTMLImageElement|null=null;
    if(docFile.mime==="application/pdf"){
      source=[...document.querySelectorAll<HTMLCanvasElement>(".doc-pdf-page canvas")].find(canvas=>{
        const rect=canvas.getBoundingClientRect();return rect.bottom>0&&rect.top<innerHeight;
      })??document.querySelector<HTMLCanvasElement>(".doc-pdf-page canvas");
    }else if(docFile.mime.startsWith("image/"))source=document.querySelector<HTMLImageElement>(".doc-image-scroll img");
    if(!source)return undefined;
    if(source instanceof HTMLImageElement&&!source.complete)return undefined;
    const width=source instanceof HTMLCanvasElement?source.width:source.naturalWidth;
    const height=source instanceof HTMLCanvasElement?source.height:source.naturalHeight;
    if(!width||!height)return undefined;
    const scale=Math.min(1,1600/Math.max(width,height));
    const canvas=document.createElement("canvas");canvas.width=Math.round(width*scale);canvas.height=Math.round(height*scale);
    const context=canvas.getContext("2d");if(!context)return undefined;
    context.drawImage(source,0,0,canvas.width,canvas.height);
    return canvas.toDataURL("image/jpeg",0.8);
  };
  const paintImage=()=>{
    const source=paintFrame.current?.contentDocument?.querySelector<HTMLCanvasElement>("#canvas_minipaint");
    if(!source?.width||!source.height)return undefined;
    const scale=Math.min(1,1600/Math.max(source.width,source.height));
    const canvas=document.createElement("canvas");canvas.width=Math.round(source.width*scale);canvas.height=Math.round(source.height*scale);
    const context=canvas.getContext("2d");if(!context)return undefined;
    context.drawImage(source,0,0,canvas.width,canvas.height);
    return canvas.toDataURL("image/jpeg",0.8);
  };
  const sendContext=async()=>{
    if(channel.current?.readyState!=="open")return;
    const board=boardOpenRef.current?await getBoardApi():null;
    if(board){
      const image=board.snapshot();
      const text=board.elements().map(e=>`[${e.id}] "${e.text}" (${Math.round(e.rect.x)},${Math.round(e.rect.y)},${Math.round(e.rect.w)},${Math.round(e.rect.h)})`).join("\n");
      sendEvent({type:"conversation.item.create",item:{type:"message",role:"user",content:[{type:"input_text",text:`Board visible elements in CSS pixels:\n${text}`},{type:"input_image",image_url:image}]}});
    }
    else if(paintMode){
      const items=paintElements();
      const active=items.find(item=>item.active||item.selected)?.text||"unknown";
      const paintDoc=paintFrame.current?.contentDocument;
      const mainColor=paintDoc?.querySelector<HTMLInputElement>("#color_hex")?.value
        ||paintDoc?.querySelector<HTMLInputElement>("input[type='color']")?.value||"unknown";
      const color=mainColor.trim().toLowerCase();
      const layerCount=items.filter(item=>item.isLayer).length;
      const dialog=items.find(item=>item.in_dialog)?.dialog||"";
      voiceLog().push({type:"paint_collector",turn:responseTurn.current||voiceState().turn,count:items.length,dialog:dialog||null,colour:color});
      const rows=items.map(item=>`[${item.id}] "${item.text}" (${Math.round(item.rect.x)},${Math.round(item.rect.y)},${Math.round(item.rect.w)},${Math.round(item.rect.h)})${item.active?" active":""}${item.selected?" selected":""}${item.in_dialog?" in_dialog:true":""}`).join("\n");
      const dialogState=dialog?`; dialog: ${JSON.stringify(dialog)}`:"";
      const content:Array<Record<string,string>>=[{type:"input_text",text:`Paint editor visible elements in top-document CSS pixels:\n${rows}\nPaint state: active tool=${active}; colour: ${color}; layer count=${layerCount}${dialogState}.`}];
      const image=paintImage();
      if(image)content.push({type:"input_image",image_url:image});
      sendEvent({type:"conversation.item.create",item:{type:"message",role:"user",content}});
    }
    else if(docMode){
      const text=elements().map(e=>`[${e.id}] "${e.text}" (${Math.round(e.rect.x)},${Math.round(e.rect.y)},${Math.round(e.rect.w)},${Math.round(e.rect.h)})`).join("\n");
      const content:Array<Record<string,string>>=[{type:"input_text",text:`Document visible elements in CSS pixels:\n${text}`}];
      const image=await documentImage();
      if(image)content.push({type:"input_image",image_url:image});
      sendEvent({type:"conversation.item.create",item:{type:"message",role:"user",content}});
    }
    else {const text=elements().map(e=>`[${e.id}] "${e.text}" (${Math.round(e.rect.x)},${Math.round(e.rect.y)},${Math.round(e.rect.w)},${Math.round(e.rect.h)})`).join("\n");sendEvent({type:"conversation.item.create",item:{type:"message",role:"user",content:[{type:"input_text",text:`TD visible elements in CSS pixels:\n${text}`} ]}});}
  };
  const pumpResponses=async()=>{
    if(!sessionReady.current||activeResponse.current||responseStartPending.current||processingTools.current||dispatchingResponse.current||channel.current?.readyState!=="open")return;
    if(pendingResponses.current.length){
      const pending=pendingResponses.current.shift()!;
      responseTurn.current=pending.turn;
      responseStartPending.current=true;
      pendingResponseTurn.current=pending.turn;
      if(!sendEvent({type:"response.create",...(pending.response?{response:pending.response}:{})})){
        responseStartPending.current=false;
        pendingResponseTurn.current=null;
        pendingResponses.current.unshift(pending);
      }
      return;
    }
    const next=queuedTurns.current.shift();
    if(!next)return;
    dispatchingResponse.current=true;
    responseTurn.current=next.turn;
    try{
      await sendContext();
      if(activeResponse.current||responseStartPending.current||processingTools.current||channel.current?.readyState!=="open"){
        queuedTurns.current.unshift(next);
        return;
      }
      if(!sendEvent({type:"conversation.item.create",item:{type:"message",role:"user",content:[{type:"input_text",text:next.text}]}})){
        queuedTurns.current.unshift(next);
        return;
      }
      responseStartPending.current=true;
      pendingResponseTurn.current=next.turn;
      if(!sendEvent({type:"response.create"})){
        responseStartPending.current=false;
        pendingResponseTurn.current=null;
        pendingResponses.current.unshift({turn:next.turn});
      }
    }finally{
      dispatchingResponse.current=false;
    }
  };
  const sendQuestion=async(q:string)=>{
    const text=q.trim();
    if(!text||channel.current?.readyState!=="open")return;
    const state=voiceState();
    const turn=++state.turn;
    voiceLog().push({type:"user",turn,text});
    queuedTurns.current.push({turn,text});
    setQuestion("");
    void pumpResponses();
  };
  const start=async(pushToTalkMode=false)=>{
    window.__geraldLog=[];
    window.__geraldState={turn:0,settledTurn:0,pendingTools:0,settledAt:0,responsesCreated:0,responsesDone:0};
    sessionReady.current=false;
    activeResponse.current=null;activeResponseTurn.current=null;responseStartPending.current=false;pendingResponseTurn.current=null;
    responseTurns.current.clear();completedResponses.current.clear();processingTools.current=false;dispatchingResponse.current=false;
    queuedTurns.current=[];pendingResponses.current=[];responseTurn.current=0;handled.current.clear();
    pushToTalk.current=pushToTalkMode;
    toggleMic.current=!pushToTalkMode;
    setVoiceError("");
    setConnecting(true);setStatus("thinking");
    try{
      stream.current=await navigator.mediaDevices.getUserMedia({audio:true});
      const micOn=!pushToTalkMode||pushToTalk.current;
      setMicEnabled(micOn);
      stream.current.getAudioTracks().forEach(track=>{track.enabled=micOn;});
      attachAnalyser(stream.current,"mic");
      const pc=new RTCPeerConnection();peer.current=pc;stream.current.getAudioTracks().forEach(t=>pc.addTrack(t,stream.current!));
      pc.ontrack=e=>{attachAnalyser(e.streams[0],"remote");if(audio.current){audio.current.srcObject=e.streams[0];void audio.current.play().catch(()=>undefined);}};
      const dc=pc.createDataChannel("oai-events");channel.current=dc;
      dc.onerror=event=>{console.error("Realtime data channel failed",event);setVoiceError("La connexion vocale a échoué.");setStatus("idle");};
      pc.onconnectionstatechange=()=>{if(pc.connectionState==="failed"){console.error("Realtime connection failed");setVoiceError("La connexion vocale a échoué.");setStatus("idle");}};
      dc.onopen=()=>{setConnecting(false);const micOn=stream.current?.getAudioTracks().some(track=>track.enabled)??false;setMicEnabled(micOn);setStatus(micOn?"listening":"idle");void sendContext();};
      dc.onmessage=message=>{
        let event:any;
        try{event=JSON.parse(message.data);}catch(error){console.error("Invalid Realtime event",error);setVoiceError("Message vocal illisible.");setStatus("idle");return;}
        console.info("[gerald voice event]",event.type);
        const state=voiceState();
        if(event.type==="session.updated"){
          sessionReady.current=true;
          voiceLog().push({type:"session_updated",turn:state.turn});
          void pumpResponses();
        }
        else if(event.type==="input_audio_buffer.speech_started"){setStatus("listening");void sendContext();}
        else if(event.type==="input_audio_buffer.speech_stopped")setStatus("thinking");
        else if(event.type==="conversation.item.input_audio_transcription.completed"){const text=String(event.transcript??"");if(text){setCaption(text);setCaptionFading(false);if(captionTimer.current)clearTimeout(captionTimer.current);captionTimer.current=window.setTimeout(()=>{setCaptionFading(true);captionTimer.current=window.setTimeout(()=>{setCaption("");setCaptionFading(false);},400);},2600);}}
        else if(event.type==="response.created"){
          const id=event.response?.id??event.response_id;
          if(activeResponse.current&&id&&activeResponse.current!=="__active__"&&activeResponse.current!==String(id)){
            const error={message:"Realtime created a response before the active response finished",active_response:activeResponse.current,new_response:String(id)};
            console.error("[gerald realtime error]",error);
            voiceLog().push({type:"error",turn:responseTurn.current||state.turn,error});
            return;
          }
          const turn=pendingResponseTurn.current??activeResponseTurn.current??(responseTurn.current||state.turn);
          activeResponse.current=String(id??"__active__");
          activeResponseTurn.current=turn;
          if(id)responseTurns.current.set(String(id),turn);
          responseStartPending.current=false;
          pendingResponseTurn.current=null;
          voiceLog().push({type:"response_created",turn,response_id:id??null});
          state.responsesCreated+=1;setStatus("thinking");setCaption("");setCaptionFading(false);if(captionTimer.current)clearTimeout(captionTimer.current);
        }
        else if(event.type==="response.output_audio_buffer.started"||event.type==="response.output_audio_transcript.delta"||event.type==="response.audio_transcript.delta"){setStatus("speaking");if(event.delta){setCaption(v=>v+event.delta);setCaptionFading(false);if(event.delta.toLowerCase().includes("au tableau"))setSuggestion(true);}}
        else if(event.type==="response.output_audio_transcript.done"||event.type==="response.audio_transcript.done"){
          const responseKey=event.response_id?String(event.response_id):null;
          const turn=(responseKey?responseTurns.current.get(responseKey):undefined)
            ??activeResponseTurn.current??(responseTurn.current||state.turn);
          voiceLog().push({type:"transcript",turn,response_id:event.response_id??null,text:String(event.transcript??"")});
        }
        else if(event.type==="response.output_audio_buffer.stopped")setStatus("idle");
        else if(event.type==="error"){
          console.error("[gerald realtime error]",event);
          voiceLog().push({type:"error",turn:responseTurn.current||state.turn,error:event.error??event});
          if(responseStartPending.current&&!activeResponse.current){responseStartPending.current=false;pendingResponseTurn.current=null;}
        }
        else if(event.type==="response.done"){
          const response=event.response??{},calls=(response.output??[]).filter((item:any)=>item.type==="function_call");
          const responseId=response.id??event.response_id;
          const responseKey=responseId?String(responseId):null;
          if(responseKey&&completedResponses.current.has(responseKey))return;
          if(calls.length&&response.id&&handled.current.has(response.id))return;
          if(responseKey&&activeResponse.current&&activeResponse.current!=="__active__"&&activeResponse.current!==responseKey){
            const error={message:"Realtime completed a response other than the active response",active_response:activeResponse.current,completed_response:responseKey};
            console.error("[gerald realtime error]",error);
            voiceLog().push({type:"error",turn:responseTurn.current||state.turn,error});
            return;
          }
          const turn=(responseKey?responseTurns.current.get(responseKey):undefined)
            ??activeResponseTurn.current??(responseTurn.current||state.turn);
          if(responseKey){completedResponses.current.add(responseKey);responseTurns.current.delete(responseKey);}
          activeResponse.current=null;
          activeResponseTurn.current=null;
          responseStartPending.current=false;
          pendingResponseTurn.current=null;
          state.responsesDone+=1;
          voiceLog().push({type:"response_done",turn,response_id:responseId??null,status:response.status??null,status_details:response.status_details??null,output_types:(response.output??[]).map((item:any)=>item.type),tool_names:calls.map((call:any)=>call.name)});
          if(response.status==="failed"){
            const error=response.status_details??response.error??{message:"Realtime response failed"};
            console.error("[gerald realtime error]",error);
            voiceLog().push({type:"error",turn,response_id:responseId??null,error});
          }
          if(calls.length){
            if(response.id)handled.current.add(response.id);
            state.pendingTools+=calls.length;
            processingTools.current=true;
            setStatus("thinking");
            void(async()=>{
              const showingTools=new Set(["point","circle","arrow","highlight"]);
              let showingCalls=0;
              try{
                for(const call of calls){
                  let args:Record<string,unknown>={},output:Record<string,unknown>;
                  const view=call.name==="open_board"?"td":boardOpenRef.current?"board":"td";
                  const isShowingTool=paintMode&&showingTools.has(call.name);
                  const rejectShowingTool=isShowingTool&&showingCalls>0;
                  if(isShowingTool)showingCalls+=1;
                  const callEntry:Record<string,unknown>={type:"tool_call",turn,call_id:call.call_id,name:call.name,arguments:call.arguments,view,args:null};
                  voiceLog().push(callEntry);
                  try{
                    args=JSON.parse(call.arguments||"{}");
                    callEntry.args=args;
                    if(rejectShowingTool){
                      output={ok:false,error:"Tu as déjà montré une commande ce tour-ci. Ne rappelle plus d'outil : dis en une phrase ce que l'élève doit faire, puis attends."};
                    }else{
                      const api=call.name==="open_board"?window.geraldTD:boardOpenRef.current?await getBoardApi():window.geraldTD;
                      output=await api?.exec(call.name,args)??{ok:false,error:"view unavailable"};
                    }
                  }catch(error){
                    console.error("Voice tool failed",error);
                    output=rejectShowingTool
                      ?{ok:false,error:"Tu as déjà montré une commande ce tour-ci. Ne rappelle plus d'outil : dis en une phrase ce que l'élève doit faire, puis attends."}
                      :{ok:false,error:String(error)};
                  }
                  if(!output.ok){console.error("Voice tool returned an error",call.name,output);setVoiceError(call.name==="plot"?"Le tracé a échoué.":"L’action a échoué.");setStatus("idle");}else setVoiceError("");
                  voiceLog().push({type:"tool_result",turn,call_id:call.call_id,name:call.name,args,view,result:output,ok:Boolean(output.ok),error:output.error??null});
                  state.pendingTools-=1;
                  console.info("[gerald voice tool]",call.name,view,Boolean(output.ok));
                  sendEvent({type:"conversation.item.create",item:{type:"function_call_output",call_id:call.call_id,output:JSON.stringify(output)}});
                }
                await sendContext();
                pendingResponses.current.push({turn,response:paintMode&&showingCalls>0?{tool_choice:"none"}:undefined});
              }catch(error){
                console.error("Voice tool response handling failed",error);
                voiceLog().push({type:"error",turn,error:String(error)});
                pendingResponses.current.push({turn,response:paintMode&&showingCalls>0?{tool_choice:"none"}:undefined});
              }finally{
                processingTools.current=false;
                void pumpResponses();
              }
            })();
            return;
          }
          if(state.pendingTools===0){state.settledTurn=Math.max(state.settledTurn,turn);state.settledAt=Date.now();}
          setStatus("idle");
          if(captionTimer.current)clearTimeout(captionTimer.current);
          captionTimer.current=window.setTimeout(()=>{setCaptionFading(true);captionTimer.current=window.setTimeout(()=>{setCaption("");setCaptionFading(false);},400);},2800);
          if(!queuedTurns.current.length)responseTurn.current=0;
          void pumpResponses();
        }
      };
      const offer=await pc.createOffer();await pc.setLocalDescription(offer);
      if(pc.iceGatheringState!=="complete")await new Promise<void>(resolve=>{const timer=setTimeout(resolve,5000);pc.addEventListener("icegatheringstatechange",()=>{if(pc.iceGatheringState==="complete"){clearTimeout(timer);resolve();}},{once:true});});
      const sessionUrl=paintMode
        ? "/api/session?mode=paint"
        : docMode
        ? `/api/session?mode=doc&title=${encodeURIComponent(docFile?.filename??`document-${docId}`)}`
        : liveMode?"/api/session?live=1":"/api/session";
      const response=await fetch(sessionUrl,{method:"POST",headers:{"Content-Type":"application/sdp"},body:pc.localDescription?.sdp??""});
      const sdp=await response.text();if(!response.ok)throw new Error(sdp||`session ${response.status}`);
      await pc.setRemoteDescription({type:"answer",sdp});
    }catch(error){console.error("Voice session failed",error);setVoiceError("Impossible de démarrer la voix.");setConnecting(false);setStatus("idle");stop();}
      };
  const stop=()=>{pushToTalk.current=false;toggleMic.current=false;sessionReady.current=false;activeResponse.current=null;activeResponseTurn.current=null;responseStartPending.current=false;pendingResponseTurn.current=null;responseTurns.current.clear();completedResponses.current.clear();processingTools.current=false;dispatchingResponse.current=false;queuedTurns.current=[];pendingResponses.current=[];responseTurn.current=0;channel.current?.close();peer.current?.close();stream.current?.getTracks().forEach(t=>t.stop());channel.current=null;peer.current=null;stream.current=null;micAnalyser.current=null;remoteAnalyser.current=null;if(audioContext.current){void audioContext.current.close();audioContext.current=null;}setAudioLevel(0);setMicEnabled(false);setConnecting(false);setStatus("idle");};
  const toggleMicrophone=()=>{
    if(channel.current?.readyState==="open"){
      const track=stream.current?.getAudioTracks()[0];
      if(!track){const error=new Error("Realtime session has no microphone track");console.error("Microphone toggle failed",error);setVoiceError("Le microphone n'est pas disponible.");setStatus("idle");return;}
      const enabled=!track.enabled;
      toggleMic.current=true;
      pushToTalk.current=false;
      track.enabled=enabled;
      setMicEnabled(enabled);
      setVoiceError("");
      setStatus(enabled?"listening":"idle");
      return;
    }
    if(!connecting)void start();
  };
  const beginPushToTalk=()=>{
    if(pushToTalk.current)return;
    pushToTalk.current=true;
    if(channel.current?.readyState==="open"){
      pttPreviousMic.current=stream.current?.getAudioTracks().some(track=>track.enabled)??false;
      stream.current?.getAudioTracks().forEach(track=>{track.enabled=true;});
      setMicEnabled(true);
      setStatus("listening");
    }else if(!connecting)void start(true);
      };
  const endPushToTalk=()=>{
    if(!pushToTalk.current)return;
    pushToTalk.current=false;
    if(!toggleMic.current){
      stream.current?.getAudioTracks().forEach(track=>{track.enabled=false;});
      setMicEnabled(false);
      if(channel.current?.readyState==="open")setStatus("thinking");
    }else{
      stream.current?.getAudioTracks().forEach(track=>{track.enabled=pttPreviousMic.current;});
      setMicEnabled(pttPreviousMic.current);
      if(channel.current?.readyState==="open")setStatus(pttPreviousMic.current?"listening":"idle");
    }
  };
  useEffect(()=>()=>{stop();if(captionTimer.current)clearTimeout(captionTimer.current);},[]);
  useEffect(()=>{
    const down=(event:KeyboardEvent)=>{if(event.ctrlKey&&event.shiftKey&&!event.repeat){event.preventDefault();beginPushToTalk();}};
    const up=(event:KeyboardEvent)=>{if(event.key==="Control"||event.key==="Shift")endPushToTalk();};
    const blur=()=>endPushToTalk();
    const message=(event:MessageEvent)=>{
      if(event.origin!==location.origin||event.data?.type!=="gerald-hotkey")return;
      if(event.source!==window.parent&&event.source!==frame.current?.contentWindow)return;
      if(event.data.pressed)beginPushToTalk();else endPushToTalk();
    };
    window.addEventListener("keydown",down);window.addEventListener("keyup",up);window.addEventListener("blur",blur);
    window.addEventListener("message",message);
    if(embedded)window.parent.postMessage({type:"gerald-ready"},location.origin);
    return()=>{window.removeEventListener("keydown",down);window.removeEventListener("keyup",up);window.removeEventListener("blur",blur);window.removeEventListener("message",message);};
  },[]);
  useEffect(()=>{
    const data=new Float32Array(512);let frame=0,last=0;
    const measure=(time:number)=>{
      const analyser=status==="listening"?micAnalyser.current:status==="speaking"?remoteAnalyser.current:null;
      let level=0;
      if(analyser){analyser.getFloatTimeDomainData(data);let sum=0;for(const sample of data)sum+=sample*sample;level=Math.min(1,Math.sqrt(sum/data.length)*12);}
      if(time-last>40){setAudioLevel(level);last=time;}
      frame=requestAnimationFrame(measure);
    };
    frame=requestAnimationFrame(measure);
    return()=>cancelAnimationFrame(frame);
  },[status]);
  useEffect(()=>{if(voiceMode)return;const onAnswer=(json:string)=>{const text=JSON.parse(json).text??"";setAnswer(v=>v&&{...v,text});};bridge.answer.connect(onAnswer);return()=>bridge.answer.disconnect?.(onAnswer);},[]);
  const sendMock=()=>{const q=question.trim();if(!q)return;const ex=exercises.find(item=>q.toLowerCase().includes(item.title.toLowerCase()))??activeExercise;setAnswer({q,text:"",ex});bridge.ask(`TD 4 — Polynômes du second degré. ${q}`);setQuestion("");};
  const onSubmit=(event:React.FormEvent)=>{event.preventDefault();if(voiceMode)void sendQuestion(question);else sendMock();};
  const clickExercise=(ex:typeof exercises[number])=>{setActiveExercise(ex);if(voiceMode)openBoard(ex.id);else bridge.openBoard(ex.title,JSON.stringify(ex.lines));};
  const sessionOpen=channel.current?.readyState==="open";
  return <main className={`td-root${docMode?" document-mode":""}${paintMode?" paint-mode":""}`}>{paintMode&&<iframe ref={paintFrame} className="paint-editor" title="miniPaint" src="/vendor/minipaint/index.html"/>}{!liveMode&&!docMode&&!paintMode&&<article className="paper"><header className="td-head" data-gerald-id="1"><div className="td-meta"><span>Lycée — Mathématiques</span><span>TD 4</span></div><h1 data-gerald-id="2">Polynômes du second degré</h1><div className="td-student"><span>Nom : __________________</span><span>Date : ________________</span></div></header>
    <section className="reminder" data-gerald-id="3"><h2 data-gerald-id="4">Rappel de cours</h2><p data-gerald-id="5">Pour <span dangerouslySetInnerHTML={{__html:katex.renderToString("ax^2+bx+c=0")}} />, le discriminant vaut <span dangerouslySetInnerHTML={{__html:katex.renderToString("\\Delta=b^2-4ac")}} />. Si <span dangerouslySetInnerHTML={{__html:katex.renderToString("\\Delta>0")}} />, l’équation possède deux racines réelles.</p></section>
    {exercises.map((ex,i)=><section className="exercise" data-gerald-id={10+i*3} key={ex.id} onClick={()=>clickExercise(ex)}><p className="exercise-lead" data-gerald-id={11+i*3}><strong>{ex.title}.</strong><span dangerouslySetInnerHTML={{__html:katex.renderToString(ex.math)}}/></p><p data-gerald-id={12+i*3}>{ex.instruction}</p><button className="open-ex">Ouvrir au tableau →</button></section>)}
  </article>}
    {docMode&&<section className="document-view" aria-label={docFile?.filename??"Document"}><h1>{docFile?.filename??"Chargement du document…"}</h1>{docFile&&<DocumentView file={docFile}/>}</section>}
    <div className="td-mark-layer" aria-hidden="true">
      <svg width={innerWidth} height={innerHeight}>
        {marks.filter(m=>m.kind==="circle").map(m=>{
          const progress=m.progress??1;
          return <g key={m.id} data-gerald-mark-kind="circle">
            <path d={pointsToPath(m.points??[])} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1-progress} style={{stroke:m.color??undefined}}/>
            <path className="sketch-ghost" d={pointsToPath(m.ghostPoints??[])} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1-progress} style={{stroke:m.color??undefined}}/>
          </g>;
        })}
        {marks.filter(m=>m.kind==="underline").map(m=><line key={m.id} data-gerald-mark-kind="underline" x1={m.rect.x-m.rect.w/2} x2={m.rect.x-m.rect.w/2+m.rect.w*(m.progress??1)} y1={m.rect.y+m.rect.h/2} y2={m.rect.y+m.rect.h/2} style={{stroke:m.color??undefined}}/>)}
        {marks.filter(m=>m.kind==="point").map(m=><circle key={m.id} data-gerald-mark-kind="point" cx={m.rect.x} cy={m.rect.y} r="5" style={{fill:m.color??undefined}}/> )}
        {marks.filter(m=>m.kind==="highlight").map(m=><rect key={m.id} data-gerald-mark-kind="highlight" x={m.rect.x-m.rect.w/2} y={m.rect.y-m.rect.h/2} width={m.rect.w*(m.progress??1)} height={m.rect.h} style={{fill:m.fill??undefined,stroke:m.color??undefined}}/>)}
        {marks.filter(m=>m.kind==="arrow"&&m.headPoints).map(m=>{
          const [wingA,tip,wingB]=m.headPoints!;
          return <g key={m.id} data-gerald-mark-kind="arrow">
            <path d={pointsToPath(m.shaftPoints??[])} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1-(m.progress??1)} style={{stroke:m.color??undefined}}/>
            <path d={`M ${wingA.x} ${wingA.y} L ${tip.x} ${tip.y} L ${wingB.x} ${wingB.y}`} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1-(m.head??1)} style={{stroke:m.color??undefined}}/>
          </g>;
        })}
        {marks.filter(m=>(m.kind==="note"||m.kind==="tip")&&m.leader&&m.annotationTarget).map(m=>{
          const line=annotationLeader(m.annotationTarget!,m.rect);
          return <line key={`${m.id}-leader`} x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} style={{stroke:m.color??undefined}}/>;
        })}
        {marks.filter(m=>m.kind==="note"||m.kind==="tip").map(m=>
          <foreignObject key={m.id} data-gerald-note={m.id} data-gerald-mark-kind={m.kind} x={m.rect.x} y={m.rect.y} width={m.rect.w} height={m.rect.h}>
            <div className={m.kind==="note"?"td-note-box":"td-tip-box"} style={m.color?{color:m.color,border:`1px solid ${m.color}`}:undefined}>{m.text}</div>
          </foreignObject>)}
        {marks.filter(m=>m.kind==="write"||m.kind==="write_math").map(m=><text key={m.id} data-gerald-mark-kind={m.kind} x={m.rect.x} y={m.rect.y} className="td-note" style={{fill:m.color??"#111"}}>{m.text}</text>)}
      </svg>
      <div className="gerald-pointer" aria-hidden="true" style={{left:Math.round(cursor.x),top:Math.round(cursor.y),opacity:cursor.visible?1:0}}><i/>Gerald</div>
    </div>
    <div className={`td-assist${liveMode||docMode?" live":""}${boardOpen?" board-open":""}`}>
      {!voiceMode&&answer&&<div className="td-answer" key={answer.q}><span className="td-q">{answer.q}</span><p>{answer.text||"…"}</p><button className="td-go" onClick={()=>clickExercise(answer.ex)}>Viens, on va au tableau · {answer.ex.title} →</button></div>}
      {voiceMode&&!liveMode&&suggestion&&<button className="td-go" onClick={()=>openBoard(activeExercise.id)}>Viens, on va au tableau · {activeExercise.title} →</button>}
      {voiceMode&&caption&&<div className={`td-caption${captionFading?" fade":""}`}><Reveal text={caption}/></div>}
      <form className="td-ask" onSubmit={onSubmit}><div className="voice-status"><Orb status={status} size={30} level={audioLevel}/>{voiceError&&<span className="td-voice-error" role="status">{voiceError}</span>}</div>
        <input data-gerald-id="30" value={question} onChange={e=>setQuestion(e.target.value)} onFocus={()=>bridge.requestFocus(true)} onBlur={()=>bridge.requestFocus(false)} placeholder={paintMode||docMode?"Demande à Gerald…":liveMode?"Pose une question à Gerald…":"Une question sur le TD ? Je t’explique."}/>
        {voiceMode
          ? <><span className="td-hold">Maintiens <kbd>Ctrl</kbd> + <kbd>Shift</kbd></span><span className={`td-wave${status==="speaking"||status==="listening"?" on":""}`} aria-hidden="true">{Array.from({length:12},(_,i)=><i key={i} style={{animationDelay:`${i*70}ms`}}/>)}</span></>
          : <kbd>CTRL + SHIFT</kbd>}
        {voiceMode&&<button type="button" className="td-mic" aria-label={sessionOpen?(micEnabled?"Couper le micro":"Activer le micro"):"Parler à Gerald"} aria-pressed={sessionOpen?micEnabled:undefined} disabled={connecting&&!sessionOpen} onClick={toggleMicrophone}>{sessionOpen?(micEnabled?"Couper le micro":"Activer le micro"):connecting?"Connexion…":"Parler à Gerald"}</button>}
        {voiceMode&&sessionOpen&&<button type="button" className="td-stop" onClick={stop}>Arrêter</button>}
      </form>
    </div>
    {voiceMode&&<div className={`td-board-overlay ${boardOpen?"open":""}`}>{docMode
      ? <button className="td-board-close" onClick={()=>{boardOpenRef.current=false;setBoardOpen(false);}}>Retour au document</button>
      : !liveMode&&<button className="td-board-close" onClick={()=>{boardOpenRef.current=false;setBoardOpen(false);}}>Retour au TD</button>}
      {boardSrc&&<iframe ref={frame} title="Tableau" src={boardSrc} />}
    </div>}
    <audio ref={audio} autoPlay/>
  </main>;
}
createRoot(document.getElementById("root")!).render(<TD/>);
if (!window.qt && !voiceMode) {
  const host = document.createElement("div");
  host.className = "preview-notch-host";
  document.body.appendChild(host);
  mountNotch(host);
}

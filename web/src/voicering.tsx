import React, { useEffect, useRef } from "react";

const vertex = "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}";
const fragment = `precision highp float;
uniform float uTime;uniform float uAmp;uniform vec2 uRes;
float bayer(vec2 c){vec2 p=floor(mod(c,8.));float i=mod(p.x,2.)+2.*mod(p.y,2.)+4.*mod(floor(p.x/2.),2.)+8.*mod(floor(p.y/2.),2.)+16.*mod(floor(p.x/4.),2.)+32.*mod(floor(p.y/4.),2.);return (i+.5)/64.;}
void main(){vec2 uv=gl_FragCoord.xy/uRes*2.-1.;float t=uTime*.5;float a=clamp(uAmp,0.,1.2);
float r=.42+a*.2+sin(t*.9)*.02;float th=.14+a*.1+sin(t*.63)*.018;float d=length(uv);
float ring=smoothstep(r+th,r,d)-smoothstep(r,r-th,d);float glow=exp(-7.*abs(d-r));float halo=exp(-3.2*d*(1.+a*.35));
float v=clamp(ring*.75+glow*.5+halo*.08,0.,1.)*smoothstep(.95,.7,d);float s=step(bayer(gl_FragCoord.xy),v);
gl_FragColor=vec4(vec3(1.)*s,s);}`;

export function VoiceRing({active, size}: {active: boolean; size: number}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const activeRef = useRef(active);
  activeRef.current = active;
  useEffect(() => {
    const el = canvas.current;
    const gl = el?.getContext("webgl", {premultipliedAlpha: false, antialias: false});
    if (!el || !gl) return;
    const shader = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s); return s; };
    const program = gl.createProgram()!;
    gl.attachShader(program, shader(gl.VERTEX_SHADER, vertex));
    gl.attachShader(program, shader(gl.FRAGMENT_SHADER, fragment));
    gl.linkProgram(program);
    gl.useProgram(program);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(program, "p");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const uTime = gl.getUniformLocation(program, "uTime"), uAmp = gl.getUniformLocation(program, "uAmp"), uRes = gl.getUniformLocation(program, "uRes");
    const ratio = window.devicePixelRatio || 1;
    el.width = el.height = Math.round(el.clientWidth * ratio);
    gl.viewport(0, 0, el.width, el.height);
    let amp = 0.06, target = 0.06, frame = 0, pump = 0;
    const beat = () => { target = activeRef.current ? 0.25 + Math.random() * 0.7 : 0.06; pump = window.setTimeout(beat, 120 + Math.random() * 80); };
    beat();
    const render = (time: number) => {
      amp += (target - amp) * 0.08;
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform1f(uTime, time * 0.001);
      gl.uniform1f(uAmp, amp);
      gl.uniform2f(uRes, el.width, el.height);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      frame = requestAnimationFrame(render);
    };
    frame = requestAnimationFrame(render);
    return () => { cancelAnimationFrame(frame); clearTimeout(pump); };
  }, [size]);
  const box = size * 1.7;
  return <canvas ref={canvas} className="voice-ring" style={{width: box, height: box, margin: (size - box) / 2}}/>;
}

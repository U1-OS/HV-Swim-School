/* Optional local WebGL water mesh. Content and CSS pool never depend on this layer. */
(() => {
  'use strict';
  const hero=document.querySelector('.immersive-hero');
  if(!hero)return;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  if(reduced.matches||navigator.connection?.saveData||(navigator.deviceMemory&&navigator.deviceMemory<4))return;
  const canvas=document.createElement('canvas');canvas.className='aquatic-canvas';canvas.setAttribute('aria-hidden','true');
  let gl;
  try{gl=canvas.getContext('webgl',{alpha:true,antialias:false,depth:true,powerPreference:'low-power'});}catch(_){return;}
  if(!gl)return;
  const vertex=`attribute vec2 p; uniform float t; uniform float aspect; uniform vec2 pointer; varying vec3 normal; varying vec3 world;
    void main(){float x=p.x,z=p.y;float a=x*.8+z*.5+t*.36,b=z*1.8-x*.2-t*.45;
    float y=sin(a)*.26+cos(b)*.11;normal=normalize(vec3(-cos(a)*.144-sin(b)*.015,1.,-cos(a)*.09+sin(b)*.135));
    world=vec3(x,y,z);vec3 v=vec3(x+pointer.x*.12,y*.78-z*.625-1.6,y*.625+z*.78-9.);
    float d=-v.z;gl_Position=vec4(v.x*1.7/aspect,v.y*1.7,(d-1.)*.8,d);}`;
  const fragment=`precision mediump float; varying vec3 normal;varying vec3 world;
    void main(){vec3 light=normalize(vec3(-.7,1.,.4));float diffuse=max(dot(normal,light),0.);
    float spec=pow(max(dot(reflect(-light,normal),normalize(vec3(0.,3.,-5.)-world)),0.),40.);
    float bands=pow(abs(sin(world.x*3.3+world.z*2.2+world.y*18.)),18.);
    vec3 color=mix(vec3(.42,.84,.96),vec3(.08,.52,.78),diffuse*.55)+vec3(.95,.99,1.)*spec*.7+vec3(.35,.82,.95)*bands*.32;
    gl_FragColor=vec4(color,.42);}`;
  const shaders=[];let program,buffer,frame=0,visible=false,lost=false,last=0,phase=0;
  try{
    for(const [type,source] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]){const shader=gl.createShader(type);shaders.push(shader);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw new Error('Shader unavailable');}
    program=gl.createProgram();shaders.forEach(s=>gl.attachShader(program,s));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error('Scene unavailable');
    const grid=matchMedia('(max-width:600px)').matches?28:48,vertices=[];
    const point=(x,z)=>vertices.push((x/grid-.5)*15,(z/grid-.5)*12);
    for(let z=0;z<grid;z++)for(let x=0;x<grid;x++){point(x,z);point(x+1,z);point(x,z+1);point(x+1,z);point(x+1,z+1);point(x,z+1);}
    buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.STATIC_DRAW);gl.useProgram(program);
    const position=gl.getAttribLocation(program,'p');gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
    const time=gl.getUniformLocation(program,'t'),aspect=gl.getUniformLocation(program,'aspect'),pointer=gl.getUniformLocation(program,'pointer');let px=0,py=0;
    const draw=at=>{frame=0;if(!active())return;if(at-last>=1000/30){const step=Math.min((at-last)/1000,.05);last=at;phase+=step;const box=hero.getBoundingClientRect(),scale=Math.min(devicePixelRatio||1,1.5);const w=Math.round(box.width*scale),h=Math.round(box.height*scale);if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.uniform1f(time,phase);gl.uniform1f(aspect,w/Math.max(h,1));gl.uniform2f(pointer,px,py);gl.drawArrays(gl.TRIANGLES,0,vertices.length/2);}frame=requestAnimationFrame(draw);};
    function active(){return visible&&!document.hidden&&!lost&&!reduced.matches&&document.documentElement.dataset.motion!=='off';}
    function sync(){if(active()){if(!frame){last=performance.now();frame=requestAnimationFrame(draw);}}else{cancelAnimationFrame(frame);frame=0;}}
    hero.prepend(canvas);hero.dataset.aquatic='ready';
    const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();},{threshold:.03});observer.observe(hero);
    const motionObserver=new MutationObserver(sync);motionObserver.observe(document.documentElement,{attributes:true,attributeFilter:['data-motion']});
    reduced.addEventListener('change',sync);document.addEventListener('visibilitychange',sync);
    hero.addEventListener('pointermove',e=>{if(e.pointerType==='touch')return;const rect=hero.getBoundingClientRect();px=(e.clientX-rect.left)/rect.width-.5;py=(e.clientY-rect.top)/rect.height-.5;},{passive:true});
    canvas.addEventListener('webglcontextlost',()=>{lost=true;sync();canvas.hidden=true;hero.dataset.aquatic='fallback';observer.disconnect();motionObserver.disconnect();});
    window.addEventListener('pagehide',()=>{cancelAnimationFrame(frame);frame=0;});
    window.addEventListener('pageshow',sync);
  }catch(_){shaders.forEach(s=>gl.deleteShader(s));if(buffer)gl.deleteBuffer(buffer);if(program)gl.deleteProgram(program);canvas.remove();hero.dataset.aquatic='fallback';}
})();

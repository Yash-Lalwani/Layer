'use client';
import { useEffect, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { Pause, Play, Check, Sparkles, ShieldCheck, CornerDownRight } from 'lucide-react';
import { useDemoStore } from '@/lib/store';
import { sources } from '@/lib/demo';
import { SourceIcon } from './source-icon';
import { Button } from './ui/button';

const slides = [
  { first:'Understand', accent:'your project.' },
  { first:'Turn scattered work', accent:'into clear answers.' },
  { first:'Turn every answer', accent:'into evidence.' },
  { first:'Turn key decisions', accent:'into project memory.' },
];
function FloatingSource({side,slide,running}:{side:'left'|'right';slide:number;running:boolean}) {
  const type=side==='left'?(slide===2?'gmail':'drive'):(slide===3?'notion':'jira');
  return <motion.div className={`floating-fragment fragment-${side}`} animate={running?{y:[0,side==='left'?-19:19,0],rotate:side==='left'?[-7,-4,-7]:[4,7,4]}:{y:0,rotate:side==='left'?-7:4}} transition={{duration:side==='left'?4.4:5.1,repeat:Infinity,ease:'easeInOut'}}><SourceIcon type={type}/><div><strong>{side==='left'?(slide===2?'Re: Phoenix launch date':'Phoenix PRD v3'):(slide===3?'Project decisions':'Payments API')}</strong><div className="skeleton w-wide"/><div className="skeleton w-small"/></div></motion.div>;
}
function ContextScene({running}:{running:boolean}) {
  return <div className="context-visual">
    <div className="scene-label">PHOENIX LAUNCH · CONNECTED CONTEXT</div>
    <div className="context-graph">
      <svg className="graph-lines" viewBox="0 0 600 235" preserveAspectRatio="none" aria-hidden="true">
        <path d="M300 117 C235 117 220 32 130 32"/><path d="M300 117 C365 117 380 32 470 32"/><path d="M300 117 C235 117 220 202 130 202"/><path d="M300 117 C365 117 380 202 470 202"/>
        {running&&<><circle r="4"><animateMotion dur="3.2s" repeatCount="indefinite" path="M130 32 C220 32 235 117 300 117"/></circle><circle r="4"><animateMotion dur="3.6s" repeatCount="indefinite" path="M470 32 C380 32 365 117 300 117"/></circle><circle r="4"><animateMotion dur="4s" repeatCount="indefinite" path="M130 202 C220 202 235 117 300 117"/></circle><circle r="4"><animateMotion dur="3.4s" repeatCount="indefinite" path="M470 202 C380 202 365 117 300 117"/></circle></>}
      </svg>
      {sources.map((source,index)=><motion.div key={source.id} className={`graph-source graph-source-${index}`} initial={{opacity:0,scale:.75}} animate={{opacity:1,scale:1,y:running?[0,index%2?-7:7,0]:0}} transition={{opacity:{delay:.3+index*.12,duration:.4},scale:{delay:.3+index*.12,duration:.5},y:{duration:3.8+index*.35,repeat:Infinity,ease:'easeInOut'}}}><SourceIcon type={source.type}/><span>{source.name}</span></motion.div>)}
      <motion.div className="graph-hub" animate={running?{scale:[1,1.055,1]}:{scale:1}} transition={{duration:3,repeat:Infinity,ease:'easeInOut'}}><img src="/layer-logo.svg" alt=""/><strong>Layer</strong><small>Connecting the dots</small></motion.div>
    </div>
    <div className="graph-answer"><Sparkles size={17}/><span>Phoenix launches on <strong>November 15.</strong></span><small>4 sources</small></div>
  </div>;
}
function EvidenceScene({running}:{running:boolean}) {
  return <div className="citation-visual">
    <div className="citation-main"><div className="scene-label">THE ANSWER</div><h3>The launch has moved to <span>November 15.</span> <span className="citation-number">4</span></h3><div className="citation-check"><ShieldCheck size={17}/> Every claim has a source</div></div>
    <motion.div className="citation-source-card" initial={{opacity:0,x:35,rotate:4}} animate={{opacity:1,x:0,rotate:0,y:running?[0,-10,0]:0}} transition={{opacity:{delay:.45,duration:.5},x:{delay:.45,duration:.6},rotate:{delay:.45,duration:.6},y:{duration:4.2,repeat:Infinity,ease:'easeInOut'}}}><div><SourceIcon type="gmail"/><span>Re: Phoenix launch date<small>Gmail · September 19</small></span><CornerDownRight size={20}/></div><p>“We’re moving launch to <mark>Nov 15</mark> to give QA another week.”</p><span className="verified"><ShieldCheck size={14}/> Supported by this source</span></motion.div>
    <div className="citation-connector" aria-hidden="true"><span>4</span><i/></div>
  </div>;
}
function MemoryScene({running}:{running:boolean}) {
  return <div className="memory-visual">
    <div className="memory-ambient" aria-hidden="true"><span>PHOENIX LAUNCH</span><span>Plans updated</span><span>Decision detected</span></div>
    <motion.div className="memory-proposal" initial={{opacity:0,y:35,scale:.93}} animate={{opacity:1,y:running?[0,-11,0]:0,scale:1}} transition={{opacity:{delay:.3,duration:.55},scale:{delay:.3,duration:.65},y:{duration:4.4,repeat:Infinity,ease:'easeInOut'}}}><div className="memory-proposal-head"><span><Sparkles size={18}/> LAYER MEMORY</span><span>YOUR CALL</span></div><h3>Worth remembering?</h3><p>Layer noticed an update to Phoenix Launch.</p><div className="memory-proposal-fact"><Check size={17}/> Phoenix launch date is November 15.</div><div className="memory-proposal-actions"><span><Check size={15}/> Approve</span><span>Edit</span><span>Skip</span></div></motion.div>
    <div className="memory-visual-foot"><ShieldCheck size={14}/> Nothing is remembered without your approval.</div>
  </div>;
}
function Scene({slide,running}:{slide:number;running:boolean}) {
  return <div className={`scene scene-${slide}`} aria-hidden="true">
    <FloatingSource side="left" slide={slide} running={running}/><FloatingSource side="right" slide={slide} running={running}/>
    <motion.div className="scene-float" animate={running?{y:[0,-13,0],rotate:[0,.7,0]}:{y:0,rotate:0}} transition={{duration:5.5,repeat:Infinity,ease:'easeInOut'}}>
      <motion.div className="scene-perspective" initial={{opacity:0,y:65,rotateX:10,rotateY:-10,rotateZ:-4,scale:.9}} animate={{opacity:1,y:0,rotateX:0,rotateY:0,rotateZ:0,scale:1}} transition={{duration:.9,delay:.12,ease:[.22,1,.36,1]}}>
        <div className={`scene-window scene-window-${slide}`}>
          {slide===1&&<><div className="window-chrome"><span><img src="/layer-logo.svg" alt=""/> Layer</span><span className="chrome-icons">— &nbsp; ◇ &nbsp; ×</span></div><ContextScene running={running}/></>}
          {slide===2&&<EvidenceScene running={running}/>}
          {slide===3&&<MemoryScene running={running}/>}
        </div>
      </motion.div>
    </motion.div>
  </div>;
}
export function Hero() {
  const {slide,paused,setSlide,setPaused}=useDemoStore();
  const reduced=useReducedMotion();
  const [pageVisible,setPageVisible]=useState(true);
  const running=!paused&&!reduced&&pageVisible;
  useEffect(()=>{const change=()=>setPageVisible(!document.hidden);document.addEventListener('visibilitychange',change);return()=>document.removeEventListener('visibilitychange',change)},[]);
  useEffect(()=>{if(!running)return;const timer=window.setTimeout(()=>setSlide((slide+1)%slides.length),slide===0?6500:6200);return()=>window.clearTimeout(timer)},[slide,running,setSlide]);
  return <section className={`hero ${slide===0?'hero-intro':'hero-feature'}`} id="overview" aria-label="Meet Layer">
    <motion.div className="hero-wash" animate={{opacity:slide===0?1:0}} transition={{duration:1.1}}/>
    <h1 className="sr-only">Layer. Your work lives everywhere. Its context lives here.</h1>
    <AnimatePresence mode="wait"><motion.div className={`hero-slide ${slide===0?'intro-slide':'feature-slide'}`} key={slide} initial={{opacity:0,y:25,filter:'blur(5px)'}} animate={{opacity:1,y:0,filter:'blur(0px)'}} exit={{opacity:0,y:-25,filter:'blur(5px)'}} transition={{duration:reduced?0:.55,ease:[.22,1,.36,1]}}>
      <div className="hero-message">{slide===0&&<p className="hero-eyebrow">Your AI-powered project partner</p>}
        <div className="hero-title" aria-hidden="true">{slides[slide].first}{slide===0?' ':<br/>}<span>{slides[slide].accent}</span></div>
        {slide===0&&<p className="hero-description">Your work lives everywhere. Its context lives here.<br className="mobile-break"/> Answers grounded in your docs, emails, tickets, and notes.</p>}
        <Button asChild className="pill hero-cta"><a href="#demo">Try Layer <span className="sr-only">homepage demo</span></a></Button>
      </div>
      {slide!==0&&<Scene slide={slide} running={!!running}/>}
    </motion.div></AnimatePresence>
    <div className="hero-controls"><div className="slide-dots" aria-label="Hero scenes">{slides.map((item,i)=><button key={i} onClick={()=>setSlide(i)} aria-label={`Show ${i===0?'intro':item.accent.replace('.','')}`} aria-current={i===slide?'true':undefined}><span/></button>)}</div><button className="pause-button" aria-label={paused||reduced?'Play animation':'Pause animation'} aria-pressed={paused||!!reduced} onClick={()=>setPaused(!paused)} disabled={!!reduced}>{paused||reduced?<Play size={14}/>:<Pause size={14}/>}</button></div>
  </section>;
}

// Static host for one complete native dbt Charts board. No chart/table markup is
// created here: native controls send state changes; this host selects an export.
(() => {
  const $=s=>document.querySelector(s), frame=$('#reader-board');
  let catalog, progress=0, person='Carl', tab='overview', entered=false, request=0, currentFile='', observer, assignedRequest=0;
  const tabs={equipped:'equipped', overview:'overview', inventory:'inventory', 'boxes-rewards':'rewards', boxes_rewards:'rewards', rewards:'rewards', history:'history'};
  const clamp=v=>Math.max(0,Math.min(1,Number(v)||0));
  const locationAt=p=>{
    const chapter=Math.min(catalog.series.chapterCount-1e-9,p*catalog.series.chapterCount);
    const book=catalog.books.find(b=>chapter>=b.startChapter-1&&chapter<b.endChapter)??catalog.books.at(-1);
    return {book,chapter:Math.floor(chapter)-book.startChapter+2,percent:Math.round(100*(chapter-book.startChapter+1)/book.chapterCount)};
  };
  function position(){
    const here=locationAt(progress);
    $('#location-chapter').textContent=`Book ${here.book.number} · Chapter ${here.chapter}`;
    $('#location-percent').textContent=`${here.percent}% through book`;
    $('#book-range').value=Math.round(progress*10000);
    $('#book-range').style.setProperty('--range-fill',`${progress*100}%`);
    $('#book-range').setAttribute('aria-valuetext',`${here.percent}% through book ${here.book.number}, chapter ${here.chapter}`);
  }
  function entry(name,view,width){return catalog.characters[name]?.[view]?.[width]?.findLast(r=>r.progress<=progress);}
  function save(){
    const u=new URL(location);u.searchParams.set('progress',String(Math.round(progress*10000)));u.searchParams.set('character',person);u.searchParams.set('tab',tab);history.replaceState(null,'',u);
  }
  async function show(){
    position();if(!entered)return;
    const token=++request, width=innerWidth<=820?'440':'1360';
    const known=Object.keys(catalog.characters).filter(name=>Object.keys(catalog.characters[name]).some(view=>entry(name,view,width)));
    if(!known.includes(person))person=known.includes('Carl')?'Carl':(known[0]??'Carl');
    if(!entry(person,tab,width))tab=Object.keys(catalog.characters[person]??{}).find(view=>entry(person,view,width))??'overview';
    const checkpoint=entry(person,tab,width);save();
    $('#chart-empty').hidden=!!checkpoint;
    if(!checkpoint){frame.hidden=true;frame.removeAttribute('srcdoc');currentFile='';return;}
    frame.hidden=false;
    if(currentFile===checkpoint.file){assignedRequest=token;return;}
    // Hide the old state immediately, including on rewind. A failed fetch must
    // never leave later-book data displayed beneath an earlier reading position.
    frame.style.visibility='hidden';frame.setAttribute('aria-busy','true');
    try{
      const response=await fetch(`boards/${checkpoint.file}.html.gz`);
      if(!response.ok)throw Error('Could not load this board.');
      const html=await new Response(response.body.pipeThrough(new DecompressionStream('gzip'))).text();
      if(token!==request)return;
      const base=new URL('boards/',location.href).href;
      assignedRequest=token;
      frame.srcdoc=html.replace('<head>',`<head><base href="${base}">`);
      currentFile=checkpoint.file;
    }catch(error){if(token===request){frame.hidden=true;$('#chart-empty').hidden=false;$('#chart-empty').textContent=error.message;currentFile='';}}
  }
  frame.addEventListener('load',()=>{
    if(assignedRequest!==request)return;
    observer?.disconnect();
    const doc=frame.contentDocument;if(!doc)return;
    const resize=()=>{frame.style.height=`${Math.ceil(doc.documentElement.scrollHeight)}px`;};
    // Measure board's own wrapper: document height includes the prior iframe
    // height and cannot shrink after switching to a shorter native tab.
    const size=()=>{const board=doc.querySelector('.dbt-charts-board');frame.style.height=`${Math.ceil(board?.getBoundingClientRect().bottom??doc.body.scrollHeight)+8}px`;};
    observer=new ResizeObserver(size);observer.observe(doc.body);size();
    frame.style.visibility='visible';frame.removeAttribute('aria-busy');
  });
  window.addEventListener('message',event=>{
    if(event.source!==frame.contentWindow||event.data?.type!=='dbt-variable-change')return;
    const vars=event.data.variables??{};
    if(typeof vars.character==='string'&&catalog.characters[vars.character])person=vars.character;
    const selected=String(vars.dossier_tab??'').toLowerCase();if(tabs[selected])tab=tabs[selected];
    if((tab==='inventory'||tab==='equipped') && vars.gear_view)tab=vars.gear_view==='equipped'?'equipped':'inventory';
    show();
  });
  $('#book-range').addEventListener('input',event=>{progress=clamp(event.target.value/10000);show();});
  $('#enter-reader').addEventListener('click',()=>{entered=true;document.body.classList.remove('choosing-position');show();});
  $('#section-jump').addEventListener('change',event=>{const value=event.target.value;if(value==='progression'){scrollTo({top:0,behavior:'smooth'});return;}tab=({character:'overview',ledger:'inventory',rewards:'rewards',history:'history'})[value]??tab;show();});
  const about=$('#about-panel');$('#about-button').addEventListener('click',()=>{about.hidden=false;$('#about-button').setAttribute('aria-expanded','true');$('#about-close').focus();});
  const close=()=>{about.hidden=true;$('#about-button').setAttribute('aria-expanded','false');$('#about-button').focus();};
  $('#about-close').addEventListener('click',close);document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!about.hidden)close();});
  let timer;addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(show,180);});
  fetch('data/reader-board.json').then(r=>{if(!r.ok)throw Error('Board catalog unavailable.');return r.json();}).then(data=>{
    catalog=data;const params=new URLSearchParams(location.search);entered=params.has('progress')&&params.get('progress').trim()!==''&&Number.isFinite(Number(params.get('progress')));
    progress=entered?clamp(Number(params.get('progress'))/10000):0;
    person=params.get('character')||'Carl';tab=tabs[params.get('tab')]||'overview';
    document.body.classList.toggle('choosing-position',!entered);document.body.classList.remove('reader-loading');
    $('#book-range').disabled=false;$('#enter-reader').disabled=false;$('#data-version').textContent=catalog.series.dataVersion;
    show();
  }).catch(error=>{document.body.classList.remove('reader-loading');$('#chart-empty').hidden=false;$('#chart-empty').textContent=error.message;});
})();

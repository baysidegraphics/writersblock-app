export default function(component) {
  const {parentElement, data, setStateValue} = component;
  const textarea=parentElement.querySelector('textarea');
  const ink=parentElement.querySelector('.wbs-page-ink');
  const counter=parentElement.querySelector('.wbs-page-count');
  const token=/\[Page Turn\]|\[PAGE TURN\]/g;
  if(document.activeElement!==textarea && textarea.value!==data.source) textarea.value=data.source;
  function paint() {
    const source=textarea.value; ink.replaceChildren();let start=0;let count=1;
    for(const hit of source.matchAll(token)) {
      ink.appendChild(document.createTextNode(source.slice(start,hit.index)));
      const span=document.createElement('span');span.className='wbs-page-turn-token';
      span.textContent=hit[0];span.dataset.nextPage=String(++count);ink.appendChild(span);
      start=hit.index+hit[0].length;
    }
    ink.appendChild(document.createTextNode(source.slice(start)+'\n'));
    ink.style.width=textarea.clientWidth+'px';ink.scrollTop=textarea.scrollTop;ink.scrollLeft=textarea.scrollLeft;
    counter.textContent=Array.from({length:count},(_,i)=>'Page '+(i+1)).join(' · ');
    counter.dataset.pageCount=String(count);
  }
  function input(){paint();setStateValue('text',textarea.value);}
  function sync(){ink.scrollTop=textarea.scrollTop;ink.scrollLeft=textarea.scrollLeft;}
  textarea.addEventListener('input',input);textarea.addEventListener('scroll',sync);
  const observer=new ResizeObserver(paint);observer.observe(textarea);paint();
  return ()=>{textarea.removeEventListener('input',input);textarea.removeEventListener('scroll',sync);observer.disconnect();};
}

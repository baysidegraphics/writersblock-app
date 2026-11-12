export default function({parentElement,data,setStateValue}) {
 const box=parentElement.querySelector('.canvas'),button=parentElement.querySelector('.insert');
 if(document.activeElement!==box && box.dataset.source!==data.html){box.innerHTML=data.html;box.dataset.source=data.html;}
 let saved=null;
 function text(node){if(node.nodeType===3)return node.textContent;if(node.tagName==='IMG')return '';if(node.tagName==='BR')return '\n';return Array.from(node.childNodes).map(text).join('');}
 function remember(){const s=getSelection();if(s.rangeCount&&box.contains(s.anchorNode))saved=s.getRangeAt(0).cloneRange();}
 box.onkeyup=remember;box.onmouseup=remember;
 function documentValue(){let offset=0,placements={};function visit(n){if(n.nodeType===3)offset+=n.textContent.length;else if(n.tagName==='IMG'){if(n.dataset.imageId)placements[n.dataset.imageId]=offset;}else if(n.tagName==='BR')offset++;else Array.from(n.childNodes).forEach(visit);}visit(box);return {text:text(box),placements};}
 box.oninput=()=>{remember();setStateValue('document',documentValue());};
 box.onbeforeinput=e=>{if(e.inputType==='insertParagraph'){e.preventDefault();document.execCommand('insertText',false,'\n');}};
 box.onpaste=e=>{e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain'));};
 button.onmousedown=e=>e.preventDefault();
 button.onclick=()=>{const r=document.createRange();r.selectNodeContents(box);if(saved)r.setEnd(saved.startContainer,saved.startOffset);else r.setEnd(box,0);const holder=document.createElement('div');holder.append(r.cloneContents());setStateValue('document',documentValue());setStateValue('cursor',text(holder).length);};
}

(()=>{var S=Object.defineProperty;var L=(o,n,t)=>n in o?S(o,n,{enumerable:!0,configurable:!0,writable:!0,value:t}):o[n]=t;var s=(o,n,t)=>L(o,typeof n!="symbol"?n+"":n,t);var f=class{constructor(n){s(this,"baseUrl");s(this,"workspaceId");s(this,"apiKey");s(this,"sessionId");s(this,"abortController");this.baseUrl=n.baseUrl.replace(/\/+$/,""),this.workspaceId=n.workspaceId,this.apiKey=n.apiKey,this.sessionId=n.sessionId}async sendMessage(n,t){this.abort(),this.abortController=new AbortController;let e=`${this.baseUrl}/api/v1/workspaces/${this.workspaceId}/chat/stream`,r={query:n,grounding_mode:"Balanced"};this.sessionId&&(r.session_id=this.sessionId);try{let i=await fetch(e,{method:"POST",headers:{"Content-Type":"application/json",Accept:"text/event-stream","X-API-Key":this.apiKey},body:$(r),signal:this.abortController.signal});if(!i.ok){let b=`HTTP error ${i.status}`;try{b=(await i.json()).error?.message||b}catch{}t.onError(b);return}if(!i.body){t.onError("ReadableStream not supported by server");return}let a=i.body.getReader(),c=new TextDecoder("utf-8"),p="",v="",k=[];for(;;){let{value:b,done:E}=await a.read();if(E)break;p+=c.decode(b,{stream:!0});let C=p.split(`
`);p=C.pop()||"";for(let T of C){let g=T.trim();if(!(!g||g.startsWith(":")||g==="data: [DONE]")&&g.startsWith("data:")){let w=g.slice(5).trim();try{let l=JSON.parse(w),h=l.type||"token";if(h==="token"){let d=l.token??l.content??"";v+=d,t.onToken(d)}else if(h==="citation"){let d=l.citation||l;t.onCitation({id:d.id||d.citation_id,document_id:d.document_id,filename:d.filename||d.document_name,page:d.page||1,snippet:d.snippet||d.text||""})}else h==="status"?t.onStatus?.(l.status||"",l.message||""):h==="done"?(l.session_id&&(this.sessionId=l.session_id),k=l.follow_up_questions||[]):h==="error"&&t.onError(l.error||"Streaming error")}catch{v+=w,t.onToken(w)}}}}t.onDone(v,k,this.sessionId)}catch(i){if(i.name==="AbortError")return;t.onError(i.message||"Network request failed")}finally{this.abortController=void 0}}abort(){this.abortController&&(this.abortController.abort(),this.abortController=void 0)}getSessionId(){return this.sessionId}};function $(o){return JSON.stringify(o)}function m(o){let n={"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"};return o.replace(/[&<>"']/g,t=>n[t])}function x(o){if(!o)return"";let n=[],t=o.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g,(r,i,a)=>{let c=n.length,p=m(a.trim());return n.push(`<pre class="code-block"><div class="code-header"><span>${m(i||"text")}</span><button class="copy-btn" data-code="${m(a.trim())}">Copy</button></div><code>${p}</code></pre>`),`__CODE_BLOCK_${c}__`});return t=m(t),t=t.replace(/`([^`]+)`/g,'<code class="inline-code">$1</code>'),t=t.replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>"),t=t.replace(/\*([^*]+)\*/g,"<em>$1</em>"),t=t.replace(/\[\^(\d+)\]/g,'<button class="cite-pill" data-cite-idx="$1">[$1]</button>'),t=t.replace(/\[Source\s+(\d+)\]/gi,'<button class="cite-pill" data-cite-idx="$1">[Source $1]</button>'),t=t.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'),t=t.replace(/^\s*[-*]\s+(.*)$/gm,"<li>$1</li>"),t=t.replace(/(<li>.*<\/li>(\n|$))+/g,'<ul class="chat-list">$&</ul>'),t=t.split(/\n\n+/).map(r=>{let i=r.trim();return i?i.startsWith("<pre")||i.startsWith("<ul")?i:`<p>${i.replace(/\n/g,"<br/>")}</p>`:""}).join(""),t=t.replace(/__CODE_BLOCK_(\d+)__/g,(r,i)=>n[Number(i)]||""),t}var M=`
:host {
  --titan-primary: #3b82f6;
  --titan-primary-hover: #2563eb;
  --titan-bg: #0f172a;
  --titan-card-bg: #1e293b;
  --titan-text: #f8fafc;
  --titan-text-muted: #94a3b8;
  --titan-border: rgba(255, 255, 255, 0.1);
  --titan-user-bubble: #2563eb;
  --titan-bot-bubble: #1e293b;
  --titan-radius: 16px;
  --titan-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: var(--titan-text);
  box-sizing: border-box;
}

:host(.theme-light) {
  --titan-bg: #ffffff;
  --titan-card-bg: #f8fafc;
  --titan-text: #0f172a;
  --titan-text-muted: #64748b;
  --titan-border: rgba(0, 0, 0, 0.1);
  --titan-user-bubble: #2563eb;
  --titan-bot-bubble: #f1f5f9;
  --titan-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
}

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

/* Floating Launcher Button */
.launcher-btn {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--titan-primary);
  color: #ffffff;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.4);
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.2s;
  z-index: 999999;
}

:host([position="bottom-left"]) .launcher-btn {
  right: auto;
  left: 24px;
}

.launcher-btn:hover {
  transform: scale(1.08);
  background: var(--titan-primary-hover);
}

.launcher-btn svg {
  width: 28px;
  height: 28px;
  fill: currentColor;
}

/* Chat Window Container */
.chat-window {
  position: fixed;
  bottom: 96px;
  right: 24px;
  width: 380px;
  height: 580px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 120px);
  background: var(--titan-bg);
  border: 1px solid var(--titan-border);
  border-radius: var(--titan-radius);
  box-shadow: var(--titan-shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 999999;
  opacity: 0;
  transform: translateY(16px) scale(0.95);
  pointer-events: none;
  transition: opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1), transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

:host([position="bottom-left"]) .chat-window {
  right: auto;
  left: 24px;
}

.chat-window.open {
  opacity: 1;
  transform: translateY(0) scale(1);
  pointer-events: auto;
}

/* Header */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background: var(--titan-card-bg);
  border-bottom: 1px solid var(--titan-border);
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bot-avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--titan-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: bold;
  font-size: 14px;
}

.header-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--titan-text);
}

.status-badge {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  margin-left: 6px;
}

.close-btn {
  background: transparent;
  border: none;
  color: var(--titan-text-muted);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  transition: background 0.15s;
}

.close-btn:hover {
  background: var(--titan-border);
  color: var(--titan-text);
}

/* Message Stream Area */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.message-row {
  display: flex;
  flex-direction: column;
  max-width: 86%;
}

.message-row.user {
  align-self: flex-end;
}

.message-row.bot {
  align-self: flex-start;
}

.message-bubble {
  padding: 12px 14px;
  border-radius: 14px;
  word-break: break-word;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}

.message-row.user .message-bubble {
  background: var(--titan-user-bubble);
  color: #ffffff;
  border-bottom-right-radius: 2px;
}

.message-row.bot .message-bubble {
  background: var(--titan-bot-bubble);
  color: var(--titan-text);
  border: 1px solid var(--titan-border);
  border-bottom-left-radius: 2px;
}

/* Citations & Sources */
.cite-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  margin: 0 2px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 4px;
  background: rgba(59, 130, 246, 0.2);
  color: var(--titan-primary);
  border: 1px solid rgba(59, 130, 246, 0.3);
  cursor: pointer;
  transition: all 0.15s;
}

.cite-pill:hover {
  background: var(--titan-primary);
  color: #ffffff;
}

.citations-sheet {
  margin-top: 10px;
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--titan-border);
  border-radius: 8px;
  font-size: 12px;
}

.citations-title {
  font-weight: 600;
  color: var(--titan-text-muted);
  margin-bottom: 6px;
}

.citation-item {
  margin-bottom: 6px;
  color: var(--titan-text-muted);
}

.citation-item strong {
  color: var(--titan-text);
}

/* Follow-up Prompts */
.followups-container {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.followup-btn {
  padding: 6px 10px;
  background: var(--titan-card-bg);
  border: 1px solid var(--titan-border);
  border-radius: 20px;
  color: var(--titan-text);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.followup-btn:hover {
  border-color: var(--titan-primary);
  color: var(--titan-primary);
}

/* Code Blocks */
.code-block {
  background: #000000;
  border-radius: 8px;
  margin: 8px 0;
  overflow-x: auto;
}

.code-header {
  display: flex;
  justify-content: space-between;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.05);
  font-size: 11px;
  color: var(--titan-text-muted);
  border-bottom: 1px solid var(--titan-border);
}

.copy-btn {
  background: transparent;
  border: none;
  color: var(--titan-text-muted);
  font-size: 11px;
  cursor: pointer;
}

.code-block code {
  display: block;
  padding: 10px;
  font-family: monospace;
  font-size: 12px;
  color: #38bdf8;
}

.inline-code {
  background: rgba(0, 0, 0, 0.3);
  padding: 2px 4px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
}

/* Input Area */
.chat-input-area {
  padding: 12px;
  background: var(--titan-card-bg);
  border-top: 1px solid var(--titan-border);
  display: flex;
  gap: 8px;
}

.chat-input {
  flex: 1;
  background: var(--titan-bg);
  border: 1px solid var(--titan-border);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  color: var(--titan-text);
  outline: none;
  resize: none;
  height: 40px;
  max-height: 100px;
}

.chat-input:focus {
  border-color: var(--titan-primary);
}

.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: var(--titan-primary);
  border: none;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.send-btn:hover {
  background: var(--titan-primary-hover);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
`;var y=class extends HTMLElement{constructor(){super();s(this,"shadow");s(this,"engine");s(this,"messages",[]);s(this,"isOpen",!1);s(this,"windowEl");s(this,"launcherBtn");s(this,"messagesEl");s(this,"inputEl");s(this,"sendBtn");this.shadow=this.attachShadow({mode:"open"})}static get observedAttributes(){return["workspace","api-key","base-url","theme","position","accent-color","bot-name"]}connectedCallback(){this.initDOM(),this.initEngine(),this.applyTheme()}attributeChangedCallback(t,e,r){e!==r&&(t==="workspace"||t==="api-key"||t==="base-url"?this.initEngine():(t==="theme"||t==="accent-color")&&this.applyTheme())}initEngine(){let t=this.getAttribute("workspace")||"",e=this.getAttribute("api-key")||"",r=this.getAttribute("base-url")||window.location.origin;t&&e&&(this.engine=new f({workspaceId:t,apiKey:e,baseUrl:r}))}applyTheme(){(this.getAttribute("theme")||"dark")==="light"?this.classList.add("theme-light"):this.classList.remove("theme-light");let e=this.getAttribute("accent-color");e&&this.style.setProperty("--titan-primary",e)}initDOM(){let t=this.getAttribute("bot-name")||"Titan Assistant";this.shadow.innerHTML=`
      <style>${M}</style>
      <button class="launcher-btn" aria-label="Open Chat">
        <svg viewBox="0 0 24 24">
          <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/>
        </svg>
      </button>

      <div class="chat-window" role="dialog">
        <div class="chat-header">
          <div class="header-brand">
            <div class="bot-avatar">TR</div>
            <div class="header-title">${u(t)}<span class="status-badge" title="Online"></span></div>
          </div>
          <button class="close-btn" aria-label="Close Chat">\u2715</button>
        </div>

        <div class="messages-container">
          <div class="message-row bot">
            <div class="message-bubble">
              <p>Hello! How can I assist you with this workspace today?</p>
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <input type="text" class="chat-input" placeholder="Ask a question..." />
          <button class="send-btn" aria-label="Send Message">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </div>
      </div>
    `,this.windowEl=this.shadow.querySelector(".chat-window"),this.launcherBtn=this.shadow.querySelector(".launcher-btn"),this.messagesEl=this.shadow.querySelector(".messages-container"),this.inputEl=this.shadow.querySelector(".chat-input"),this.sendBtn=this.shadow.querySelector(".send-btn"),this.launcherBtn.addEventListener("click",()=>this.toggleChat()),this.shadow.querySelector(".close-btn")?.addEventListener("click",()=>this.toggleChat(!1)),this.inputEl.addEventListener("keydown",e=>{e.key==="Enter"&&!e.shiftKey&&(e.preventDefault(),this.handleSend())}),this.sendBtn.addEventListener("click",()=>this.handleSend()),this.messagesEl.addEventListener("click",e=>{let r=e.target;if(r.classList.contains("copy-btn")){let i=r.getAttribute("data-code")||"";navigator.clipboard.writeText(i).then(()=>{r.innerText="Copied!",setTimeout(()=>r.innerText="Copy",2e3)})}else if(r.classList.contains("followup-btn")){let i=r.innerText.trim();this.inputEl.value=i,this.handleSend()}})}toggleChat(t){this.isOpen=t!==void 0?t:!this.isOpen,this.isOpen?(this.windowEl.classList.add("open"),setTimeout(()=>this.inputEl.focus(),150)):this.windowEl.classList.remove("open")}async handleSend(){let t=this.inputEl.value.trim();if(!t)return;if(!this.engine){this.appendMessage({role:"bot",content:"Error: Missing workspace or API key attribute on <titan-chat>."});return}this.inputEl.value="",this.sendBtn.disabled=!0,this.appendMessage({role:"user",content:t});let e={role:"bot",content:"",citations:[],isStreaming:!0};this.messages.push(e);let r=this.createMessageElement(e);this.messagesEl.appendChild(r),this.scrollToBottom();let i=r.querySelector(".message-bubble");await this.engine.sendMessage(t,{onToken:a=>{e.content+=a,i.innerHTML=x(e.content),this.scrollToBottom()},onCitation:a=>{e.citations||(e.citations=[]),e.citations.push(a)},onDone:(a,c)=>{e.isStreaming=!1,e.followUps=c,this.renderFinalBotMessage(r,e),this.sendBtn.disabled=!1,this.scrollToBottom()},onError:a=>{e.isStreaming=!1,i.innerHTML=`<span style="color:#ef4444;">Error: ${u(a)}</span>`,this.sendBtn.disabled=!1,this.scrollToBottom()}})}appendMessage(t){this.messages.push(t);let e=this.createMessageElement(t);this.messagesEl.appendChild(e),this.scrollToBottom()}createMessageElement(t){let e=document.createElement("div");return e.className=`message-row ${t.role}`,e.innerHTML=`<div class="message-bubble">${x(t.content)}</div>`,e}renderFinalBotMessage(t,e){let r=t.querySelector(".message-bubble");if(r.innerHTML=x(e.content),e.citations&&e.citations.length>0){let i=document.createElement("div");i.className="citations-sheet",i.innerHTML=`
        <div class="citations-title">Sources & References (${e.citations.length})</div>
        ${e.citations.map((a,c)=>`
          <div class="citation-item">
            [${c+1}] <strong>${u(a.filename||"Document")}</strong> (Page ${a.page||1}):
            <em>"${u((a.snippet||"").slice(0,100))}..."</em>
          </div>
        `).join("")}
      `,r.appendChild(i)}if(e.followUps&&e.followUps.length>0){let i=document.createElement("div");i.className="followups-container",i.innerHTML=e.followUps.map(a=>`<button class="followup-btn">${u(a)}</button>`).join(""),t.appendChild(i)}}scrollToBottom(){this.messagesEl.scrollTop=this.messagesEl.scrollHeight}};function u(o){return o.replace(/[&<>"']/g,"")}typeof window<"u"&&!customElements.get("titan-chat")&&customElements.define("titan-chat",y);})();

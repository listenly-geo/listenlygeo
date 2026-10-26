import{r as e}from"./rolldown-runtime-CpWojdLp.js";import{d as t,f as n,r,t as i}from"./jsx-runtime-Ckp6R6zc.js";import{n as a,r as o,t as s}from"./save-_EK0iDwN.js";import{n as c,t as l}from"./eye-nfphIP93.js";import{t as u}from"./plus-DR5eclhK.js";import{t as d}from"./trash-2-CdDHN76c.js";import{X as f,a as p}from"./app-1FquKH63.js";var m=f(),h=e(t(),1),g=i();function _(e){let t=(0,m.c)(18),{sections:i}=e,[s,f]=(0,h.useState)(null),[_,S]=(0,h.useState)(null),[C,w]=(0,h.useState)(null),[T,E]=(0,h.useState)(!1),D;t[0]===Symbol.for(`react.memo_cache_sentinel`)?(D=e=>{S(e.id),w(e),f(e.id)},t[0]=D):D=t[0];let O=D,k;t[1]===Symbol.for(`react.memo_cache_sentinel`)?(k=()=>{S(null),w(null),E(!1)},t[1]=k):k=t[1];let A=k,j;t[2]!==C||t[3]!==T?(j=()=>{C&&(T?n.post(`/admin/landing-content`,C,{onSuccess:()=>{A()}}):n.patch(`/admin/landing-content/${C.id}`,C,{onSuccess:()=>{A()}}))},t[2]=C,t[3]=T,t[4]=j):j=t[4];let M=j,N=y,P=v,F;t[5]===Symbol.for(`react.memo_cache_sentinel`)?(F=()=>{w({section:``,label:``,kicker:``,title:``,subtitle:``,description:``,data:{},is_active:!0}),E(!0),S(0)},t[5]=F):F=t[5];let I=F,L;t[6]===Symbol.for(`react.memo_cache_sentinel`)?(L=(0,g.jsx)(r,{title:`Landing Content CMS`}),t[6]=L):L=t[6];let R;t[7]===Symbol.for(`react.memo_cache_sentinel`)?(R=(0,g.jsx)(p,{eyebrow:`Landing Content`,title:`Landing Page CMS`,description:`Manage all landing page content from here`,actions:(0,g.jsxs)(`button`,{type:`button`,onClick:I,className:`admin-primary-link`,children:[`Add Section `,(0,g.jsx)(u,{size:14})]})}),t[7]=R):R=t[7];let z;t[8]!==_||t[9]!==s||t[10]!==C||t[11]!==M||t[12]!==T||t[13]!==i?(z=(0,g.jsx)(`div`,{className:`admin-container`,children:(0,g.jsx)(`div`,{className:`admin-section`,children:i.length===0&&!T?(0,g.jsxs)(`div`,{className:`admin-empty-state`,children:[(0,g.jsx)(`p`,{children:`No landing content sections yet. Create your first one!`}),(0,g.jsxs)(`button`,{onClick:I,className:`admin-btn admin-btn-primary`,children:[(0,g.jsx)(u,{size:16}),`Create Section`]})]}):(0,g.jsxs)(`div`,{className:`landing-cms-list`,children:[T&&(0,g.jsx)(b,{data:C,setData:w,onSave:M,onCancel:A,isNew:!0}),i.map(e=>(0,g.jsxs)(`div`,{className:`landing-cms-card ${s===e.id?`expanded`:``} ${e.is_active?``:`inactive`}`,children:[(0,g.jsxs)(`div`,{className:`landing-cms-header`,children:[(0,g.jsx)(`div`,{className:`landing-cms-header-content`,onClick:()=>f(s===e.id?null:e.id),children:(0,g.jsxs)(`div`,{className:`landing-cms-title-group`,children:[(0,g.jsx)(o,{size:18,className:`chevron-icon ${s===e.id?`rotated`:``}`}),(0,g.jsxs)(`div`,{children:[(0,g.jsx)(`h3`,{className:`landing-cms-card-title`,children:e.label}),(0,g.jsxs)(`p`,{className:`landing-cms-card-meta`,children:[(0,g.jsx)(`code`,{children:e.section}),` •`,` `,e.updated_at]})]})]})}),(0,g.jsxs)(`div`,{className:`landing-cms-actions`,children:[(0,g.jsx)(`button`,{onClick:()=>P(e),className:`admin-icon-btn ${e.is_active?`active`:``}`,title:e.is_active?`Hide`:`Show`,children:e.is_active?(0,g.jsx)(l,{size:18}):(0,g.jsx)(c,{size:18})}),_!==e.id&&(0,g.jsxs)(g.Fragment,{children:[(0,g.jsx)(`button`,{onClick:()=>O(e),className:`admin-icon-btn`,title:`Edit`,children:(0,g.jsx)(a,{size:18})}),(0,g.jsx)(`button`,{onClick:()=>N(e.id),className:`admin-icon-btn admin-icon-btn-danger`,title:`Delete`,children:(0,g.jsx)(d,{size:18})})]})]})]}),s===e.id&&(0,g.jsx)(`div`,{className:`landing-cms-content`,children:_===e.id?(0,g.jsx)(b,{data:C,setData:w,onSave:M,onCancel:A}):(0,g.jsx)(x,{section:e})})]},e.id))]})})}),t[8]=_,t[9]=s,t[10]=C,t[11]=M,t[12]=T,t[13]=i,t[14]=z):z=t[14];let B;t[15]===Symbol.for(`react.memo_cache_sentinel`)?(B=(0,g.jsx)(`style`,{children:`
                .landing-cms-list {
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                }

                .landing-cms-card {
                    border: 1px solid #e5e7eb;
                    border-radius: 12px;
                    background: white;
                    overflow: hidden;
                    transition: all 0.2s ease;
                }

                .landing-cms-card.expanded {
                    border-color: #1f4c40;
                    box-shadow: 0 4px 12px rgba(31, 76, 64, 0.08);
                }

                .landing-cms-card.inactive {
                    opacity: 0.6;
                    background: #f9fafb;
                }

                .landing-cms-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 16px;
                    cursor: pointer;
                    user-select: none;
                }

                .landing-cms-header-content {
                    flex: 1;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    min-width: 0;
                }

                .landing-cms-title-group {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    flex: 1;
                    min-width: 0;
                }

                .chevron-icon {
                    flex-shrink: 0;
                    color: #6b7280;
                    transition: transform 0.2s ease;
                }

                .chevron-icon.rotated {
                    transform: rotate(180deg);
                }

                .landing-cms-card-title {
                    font-size: 15px;
                    font-weight: 600;
                    color: #111827;
                    margin: 0;
                }

                .landing-cms-card-meta {
                    font-size: 13px;
                    color: #6b7280;
                    margin: 4px 0 0;
                    display: flex;
                    gap: 8px;
                    align-items: center;
                }

                .landing-cms-card-meta code {
                    background: #f3f4f6;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                }

                .landing-cms-actions {
                    display: flex;
                    gap: 8px;
                    align-items: center;
                    flex-shrink: 0;
                }

                .landing-cms-content {
                    border-top: 1px solid #e5e7eb;
                    padding: 20px;
                    background: #fafbfc;
                }

                .landing-content-form {
                    display: flex;
                    flex-direction: column;
                    gap: 20px;
                }

                .form-group {
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                }

                .form-label {
                    font-size: 14px;
                    font-weight: 600;
                    color: #374151;
                }

                .form-input,
                .form-textarea {
                    padding: 10px 12px;
                    border: 1px solid #d1d5db;
                    border-radius: 8px;
                    font-size: 14px;
                    font-family: inherit;
                    transition: border-color 0.2s ease;
                }

                .form-input:focus,
                .form-textarea:focus {
                    outline: none;
                    border-color: #1f4c40;
                    background: white;
                }

                .form-textarea {
                    resize: vertical;
                    min-height: 100px;
                }

                .form-actions {
                    display: flex;
                    gap: 10px;
                    justify-content: flex-end;
                    padding-top: 10px;
                    border-top: 1px solid #e5e7eb;
                }

                .landing-content-preview {
                    display: flex;
                    flex-direction: column;
                    gap: 16px;
                }

                .preview-row {
                    display: flex;
                    flex-direction: column;
                    gap: 4px;
                }

                .preview-label {
                    font-size: 12px;
                    font-weight: 600;
                    color: #6b7280;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }

                .preview-value {
                    font-size: 14px;
                    color: #111827;
                    padding: 8px 12px;
                    background: white;
                    border-radius: 6px;
                    border: 1px solid #e5e7eb;
                    white-space: pre-wrap;
                    word-break: break-word;
                    font-family: 'Courier New', monospace;
                }

                .preview-value.empty {
                    color: #9ca3af;
                    font-style: italic;
                }

                @media (max-width: 860px) {
                    .landing-cms-header {
                        flex-wrap: wrap;
                    }

                    .landing-cms-actions {
                        width: 100%;
                        margin-top: 12px;
                        padding-top: 12px;
                        border-top: 1px solid #e5e7eb;
                    }
                }
            `}),t[15]=B):B=t[15];let V;return t[16]===z?V=t[17]:(V=(0,g.jsxs)(g.Fragment,{children:[L,R,z,B]}),t[16]=z,t[17]=V),V}function v(e){n.patch(`/admin/landing-content/${e.id}`,{is_active:!e.is_active})}function y(e){confirm(`Are you sure you want to delete this section?`)&&n.delete(`/admin/landing-content/${e}`)}function b(e){let t=(0,m.c)(63),{data:n,setData:r,onSave:i,onCancel:a,isNew:o}=e,c=o===void 0?!1:o;if(!n)return null;let l;t[0]===Symbol.for(`react.memo_cache_sentinel`)?(l={display:`grid`,gridTemplateColumns:`1fr 1fr`,gap:`16px`},t[0]=l):l=t[0];let u;t[1]===Symbol.for(`react.memo_cache_sentinel`)?(u=(0,g.jsx)(`label`,{className:`form-label`,children:`Section ID`}),t[1]=u):u=t[1];let d=n.section||``,f;t[2]!==n||t[3]!==r?(f=e=>r({...n,section:e.target.value}),t[2]=n,t[3]=r,t[4]=f):f=t[4];let p=!c,h;t[5]!==d||t[6]!==f||t[7]!==p?(h=(0,g.jsxs)(`div`,{className:`form-group`,children:[u,(0,g.jsx)(`input`,{type:`text`,className:`form-input`,value:d,onChange:f,placeholder:`e.g., hero, pricing, integrations`,disabled:p})]}),t[5]=d,t[6]=f,t[7]=p,t[8]=h):h=t[8];let _;t[9]===Symbol.for(`react.memo_cache_sentinel`)?(_=(0,g.jsx)(`label`,{className:`form-label`,children:`Display Label`}),t[9]=_):_=t[9];let v=n.label||``,y;t[10]!==n||t[11]!==r?(y=e=>r({...n,label:e.target.value}),t[10]=n,t[11]=r,t[12]=y):y=t[12];let b;t[13]!==y||t[14]!==v?(b=(0,g.jsxs)(`div`,{className:`form-group`,children:[_,(0,g.jsx)(`input`,{type:`text`,className:`form-input`,value:v,onChange:y,placeholder:`e.g., Hero Section`})]}),t[13]=y,t[14]=v,t[15]=b):b=t[15];let x;t[16]!==b||t[17]!==h?(x=(0,g.jsxs)(`div`,{style:l,children:[h,b]}),t[16]=b,t[17]=h,t[18]=x):x=t[18];let S;t[19]===Symbol.for(`react.memo_cache_sentinel`)?(S=(0,g.jsx)(`label`,{className:`form-label`,children:`Kicker (Small Label)`}),t[19]=S):S=t[19];let C=n.kicker||``,w;t[20]!==n||t[21]!==r?(w=e=>r({...n,kicker:e.target.value}),t[20]=n,t[21]=r,t[22]=w):w=t[22];let T;t[23]!==C||t[24]!==w?(T=(0,g.jsxs)(`div`,{className:`form-group`,children:[S,(0,g.jsx)(`input`,{type:`text`,className:`form-input`,value:C,onChange:w,placeholder:`e.g., Getting Started`})]}),t[23]=C,t[24]=w,t[25]=T):T=t[25];let E;t[26]===Symbol.for(`react.memo_cache_sentinel`)?(E=(0,g.jsx)(`label`,{className:`form-label`,children:`Title`}),t[26]=E):E=t[26];let D=n.title||``,O;t[27]!==n||t[28]!==r?(O=e=>r({...n,title:e.target.value}),t[27]=n,t[28]=r,t[29]=O):O=t[29];let k;t[30]!==D||t[31]!==O?(k=(0,g.jsxs)(`div`,{className:`form-group`,children:[E,(0,g.jsx)(`input`,{type:`text`,className:`form-input`,value:D,onChange:O,placeholder:`Main heading`})]}),t[30]=D,t[31]=O,t[32]=k):k=t[32];let A;t[33]===Symbol.for(`react.memo_cache_sentinel`)?(A=(0,g.jsx)(`label`,{className:`form-label`,children:`Subtitle`}),t[33]=A):A=t[33];let j=n.subtitle||``,M;t[34]!==n||t[35]!==r?(M=e=>r({...n,subtitle:e.target.value}),t[34]=n,t[35]=r,t[36]=M):M=t[36];let N;t[37]!==j||t[38]!==M?(N=(0,g.jsxs)(`div`,{className:`form-group`,children:[A,(0,g.jsx)(`input`,{type:`text`,className:`form-input`,value:j,onChange:M,placeholder:`Secondary heading`})]}),t[37]=j,t[38]=M,t[39]=N):N=t[39];let P;t[40]===Symbol.for(`react.memo_cache_sentinel`)?(P=(0,g.jsx)(`label`,{className:`form-label`,children:`Description`}),t[40]=P):P=t[40];let F=n.description||``,I;t[41]!==n||t[42]!==r?(I=e=>r({...n,description:e.target.value}),t[41]=n,t[42]=r,t[43]=I):I=t[43];let L;t[44]!==F||t[45]!==I?(L=(0,g.jsxs)(`div`,{className:`form-group`,children:[P,(0,g.jsx)(`textarea`,{className:`form-textarea`,value:F,onChange:I,placeholder:`Detailed description...`})]}),t[44]=F,t[45]=I,t[46]=L):L=t[46];let R;t[47]===a?R=t[48]:(R=(0,g.jsx)(`button`,{onClick:a,className:`admin-btn admin-btn-secondary`,children:`Cancel`}),t[47]=a,t[48]=R);let z;t[49]===Symbol.for(`react.memo_cache_sentinel`)?(z=(0,g.jsx)(s,{size:16}),t[49]=z):z=t[49];let B=c?`Create`:`Save`,V;t[50]!==i||t[51]!==B?(V=(0,g.jsxs)(`button`,{onClick:i,className:`admin-btn admin-btn-primary`,children:[z,B,` Section`]}),t[50]=i,t[51]=B,t[52]=V):V=t[52];let H;t[53]!==R||t[54]!==V?(H=(0,g.jsxs)(`div`,{className:`form-actions`,children:[R,V]}),t[53]=R,t[54]=V,t[55]=H):H=t[55];let U;return t[56]!==x||t[57]!==T||t[58]!==k||t[59]!==N||t[60]!==L||t[61]!==H?(U=(0,g.jsxs)(`div`,{className:`landing-content-form`,children:[x,T,k,N,L,H]}),t[56]=x,t[57]=T,t[58]=k,t[59]=N,t[60]=L,t[61]=H,t[62]=U):U=t[62],U}function x(e){let t=(0,m.c)(21),{section:n}=e,r;t[0]===n.kicker?r=t[1]:(r=n.kicker&&(0,g.jsxs)(`div`,{className:`preview-row`,children:[(0,g.jsx)(`div`,{className:`preview-label`,children:`Kicker`}),(0,g.jsx)(`div`,{className:`preview-value`,children:n.kicker})]}),t[0]=n.kicker,t[1]=r);let i;t[2]===n.title?i=t[3]:(i=n.title&&(0,g.jsxs)(`div`,{className:`preview-row`,children:[(0,g.jsx)(`div`,{className:`preview-label`,children:`Title`}),(0,g.jsx)(`div`,{className:`preview-value`,children:n.title})]}),t[2]=n.title,t[3]=i);let a;t[4]===n.subtitle?a=t[5]:(a=n.subtitle&&(0,g.jsxs)(`div`,{className:`preview-row`,children:[(0,g.jsx)(`div`,{className:`preview-label`,children:`Subtitle`}),(0,g.jsx)(`div`,{className:`preview-value`,children:n.subtitle})]}),t[4]=n.subtitle,t[5]=a);let o;t[6]===n.description?o=t[7]:(o=n.description&&(0,g.jsxs)(`div`,{className:`preview-row`,children:[(0,g.jsx)(`div`,{className:`preview-label`,children:`Description`}),(0,g.jsx)(`div`,{className:`preview-value`,children:n.description})]}),t[6]=n.description,t[7]=o);let s;t[8]===n.data?s=t[9]:(s=Object.keys(n.data).length>0&&(0,g.jsxs)(`div`,{className:`preview-row`,children:[(0,g.jsx)(`div`,{className:`preview-label`,children:`Data`}),(0,g.jsx)(`div`,{className:`preview-value`,children:JSON.stringify(n.data,null,2)})]}),t[8]=n.data,t[9]=s);let c;t[10]!==n.data||t[11]!==n.description||t[12]!==n.title?(c=!n.title&&!n.description&&Object.keys(n.data).length===0&&(0,g.jsx)(`div`,{className:`preview-row`,children:(0,g.jsx)(`div`,{className:`preview-value empty`,children:`No content yet`})}),t[10]=n.data,t[11]=n.description,t[12]=n.title,t[13]=c):c=t[13];let l;return t[14]!==r||t[15]!==i||t[16]!==a||t[17]!==o||t[18]!==s||t[19]!==c?(l=(0,g.jsxs)(`div`,{className:`landing-content-preview`,children:[r,i,a,o,s,c]}),t[14]=r,t[15]=i,t[16]=a,t[17]=o,t[18]=s,t[19]=c,t[20]=l):l=t[20],l}export{_ as default};
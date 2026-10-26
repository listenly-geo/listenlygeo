import{r as e}from"./rolldown-runtime-CpWojdLp.js";import{d as t,f as n,r,s as i,t as a}from"./jsx-runtime-Ckp6R6zc.js";import{n as o,r as s,t as c}from"./save-_EK0iDwN.js";import{n as l,t as u}from"./eye-nfphIP93.js";import{t as d}from"./plus-DR5eclhK.js";import{t as f}from"./trash-2-CdDHN76c.js";import{H as p,T as m,X as h,a as g,r as _}from"./app-1FquKH63.js";var v=p(`Link2`,[[`path`,{d:`M9 17H7A5 5 0 0 1 7 7h2`,key:`8i5ue5`}],[`path`,{d:`M15 7h2a5 5 0 1 1 0 10h-2`,key:`1b9ql8`}],[`line`,{x1:`8`,x2:`16`,y1:`12`,y2:`12`,key:`1jonct`}]]),y=h(),b=e(t(),1),x=a();function S(e){let t=(0,y.c)(21),{sections:i,landingSettings:a}=e,[c,p]=(0,b.useState)(null),[m,h]=(0,b.useState)(null),[_,v]=(0,b.useState)(null),[S,D]=(0,b.useState)(!1),k;t[0]===Symbol.for(`react.memo_cache_sentinel`)?(k=e=>{h(e.id),v(e),p(e.id)},t[0]=k):k=t[0];let A=k,j;t[1]===Symbol.for(`react.memo_cache_sentinel`)?(j=()=>{h(null),v(null),D(!1)},t[1]=j):j=t[1];let M=j,N;t[2]!==_||t[3]!==S?(N=()=>{_&&(S?n.post(`/admin/landing-content`,_,{onSuccess:()=>{M()}}):n.patch(`/admin/landing-content/${_.id}`,_,{onSuccess:()=>{M()}}))},t[2]=_,t[3]=S,t[4]=N):N=t[4];let P=N,F=w,I=C,L;t[5]===Symbol.for(`react.memo_cache_sentinel`)?(L=()=>{v({section:``,label:``,kicker:``,title:``,subtitle:``,description:``,data:{},is_active:!0}),D(!0),h(0)},t[5]=L):L=t[5];let R=L,z;t[6]===Symbol.for(`react.memo_cache_sentinel`)?(z=(0,x.jsx)(r,{title:`Landing Content CMS`}),t[6]=z):z=t[6];let B;t[7]===Symbol.for(`react.memo_cache_sentinel`)?(B=(0,x.jsx)(g,{eyebrow:`Landing Content`,title:`Landing Page CMS`,description:`Manage all landing page content from here`,actions:(0,x.jsxs)(`button`,{type:`button`,onClick:R,className:`admin-primary-link`,children:[`Add Section `,(0,x.jsx)(d,{size:14})]})}),t[7]=B):B=t[7];let V;t[8]===a?V=t[9]:(V=(0,x.jsx)(O,{landingSettings:a}),t[8]=a,t[9]=V);let H;t[10]!==m||t[11]!==c||t[12]!==_||t[13]!==P||t[14]!==S||t[15]!==i?(H=(0,x.jsx)(`div`,{className:`admin-container`,children:(0,x.jsx)(`div`,{className:`admin-section`,children:i.length===0&&!S?(0,x.jsxs)(`div`,{className:`admin-empty-state`,children:[(0,x.jsx)(`p`,{children:`No landing content sections yet. Create your first one!`}),(0,x.jsxs)(`button`,{onClick:R,className:`admin-btn admin-btn-primary`,children:[(0,x.jsx)(d,{size:16}),`Create Section`]})]}):(0,x.jsxs)(`div`,{className:`landing-cms-list`,children:[S&&(0,x.jsx)(T,{data:_,setData:v,onSave:P,onCancel:M,isNew:!0}),i.map(e=>(0,x.jsxs)(`div`,{className:`landing-cms-card ${c===e.id?`expanded`:``} ${e.is_active?``:`inactive`}`,children:[(0,x.jsxs)(`div`,{className:`landing-cms-header`,children:[(0,x.jsx)(`div`,{className:`landing-cms-header-content`,onClick:()=>p(c===e.id?null:e.id),children:(0,x.jsxs)(`div`,{className:`landing-cms-title-group`,children:[(0,x.jsx)(s,{size:18,className:`chevron-icon ${c===e.id?`rotated`:``}`}),(0,x.jsxs)(`div`,{children:[(0,x.jsx)(`h3`,{className:`landing-cms-card-title`,children:e.label}),(0,x.jsxs)(`p`,{className:`landing-cms-card-meta`,children:[(0,x.jsx)(`code`,{children:e.section}),` •`,` `,e.updated_at]})]})]})}),(0,x.jsxs)(`div`,{className:`landing-cms-actions`,children:[(0,x.jsx)(`button`,{onClick:()=>I(e),className:`admin-icon-btn ${e.is_active?`active`:``}`,title:e.is_active?`Hide`:`Show`,children:e.is_active?(0,x.jsx)(u,{size:18}):(0,x.jsx)(l,{size:18})}),m!==e.id&&(0,x.jsxs)(x.Fragment,{children:[(0,x.jsx)(`button`,{onClick:()=>A(e),className:`admin-icon-btn`,title:`Edit`,children:(0,x.jsx)(o,{size:18})}),(0,x.jsx)(`button`,{onClick:()=>F(e.id),className:`admin-icon-btn admin-icon-btn-danger`,title:`Delete`,children:(0,x.jsx)(f,{size:18})})]})]})]}),c===e.id&&(0,x.jsx)(`div`,{className:`landing-cms-content`,children:m===e.id?(0,x.jsx)(T,{data:_,setData:v,onSave:P,onCancel:M}):(0,x.jsx)(E,{section:e})})]},e.id))]})})}),t[10]=m,t[11]=c,t[12]=_,t[13]=P,t[14]=S,t[15]=i,t[16]=H):H=t[16];let U;t[17]===Symbol.for(`react.memo_cache_sentinel`)?(U=(0,x.jsx)(`style`,{children:`
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
            `}),t[17]=U):U=t[17];let W;return t[18]!==V||t[19]!==H?(W=(0,x.jsxs)(x.Fragment,{children:[z,B,V,H,U]}),t[18]=V,t[19]=H,t[20]=W):W=t[20],W}function C(e){n.patch(`/admin/landing-content/${e.id}`,{is_active:!e.is_active})}function w(e){confirm(`Are you sure you want to delete this section?`)&&n.delete(`/admin/landing-content/${e}`)}function T(e){let t=(0,y.c)(63),{data:n,setData:r,onSave:i,onCancel:a,isNew:o}=e,s=o===void 0?!1:o;if(!n)return null;let l;t[0]===Symbol.for(`react.memo_cache_sentinel`)?(l={display:`grid`,gridTemplateColumns:`1fr 1fr`,gap:`16px`},t[0]=l):l=t[0];let u;t[1]===Symbol.for(`react.memo_cache_sentinel`)?(u=(0,x.jsx)(`label`,{className:`form-label`,children:`Section ID`}),t[1]=u):u=t[1];let d=n.section||``,f;t[2]!==n||t[3]!==r?(f=e=>r({...n,section:e.target.value}),t[2]=n,t[3]=r,t[4]=f):f=t[4];let p=!s,m;t[5]!==d||t[6]!==f||t[7]!==p?(m=(0,x.jsxs)(`div`,{className:`form-group`,children:[u,(0,x.jsx)(`input`,{type:`text`,className:`form-input`,value:d,onChange:f,placeholder:`e.g., hero, pricing, integrations`,disabled:p})]}),t[5]=d,t[6]=f,t[7]=p,t[8]=m):m=t[8];let h;t[9]===Symbol.for(`react.memo_cache_sentinel`)?(h=(0,x.jsx)(`label`,{className:`form-label`,children:`Display Label`}),t[9]=h):h=t[9];let g=n.label||``,_;t[10]!==n||t[11]!==r?(_=e=>r({...n,label:e.target.value}),t[10]=n,t[11]=r,t[12]=_):_=t[12];let v;t[13]!==_||t[14]!==g?(v=(0,x.jsxs)(`div`,{className:`form-group`,children:[h,(0,x.jsx)(`input`,{type:`text`,className:`form-input`,value:g,onChange:_,placeholder:`e.g., Hero Section`})]}),t[13]=_,t[14]=g,t[15]=v):v=t[15];let b;t[16]!==v||t[17]!==m?(b=(0,x.jsxs)(`div`,{style:l,children:[m,v]}),t[16]=v,t[17]=m,t[18]=b):b=t[18];let S;t[19]===Symbol.for(`react.memo_cache_sentinel`)?(S=(0,x.jsx)(`label`,{className:`form-label`,children:`Kicker (Small Label)`}),t[19]=S):S=t[19];let C=n.kicker||``,w;t[20]!==n||t[21]!==r?(w=e=>r({...n,kicker:e.target.value}),t[20]=n,t[21]=r,t[22]=w):w=t[22];let T;t[23]!==C||t[24]!==w?(T=(0,x.jsxs)(`div`,{className:`form-group`,children:[S,(0,x.jsx)(`input`,{type:`text`,className:`form-input`,value:C,onChange:w,placeholder:`e.g., Getting Started`})]}),t[23]=C,t[24]=w,t[25]=T):T=t[25];let E;t[26]===Symbol.for(`react.memo_cache_sentinel`)?(E=(0,x.jsx)(`label`,{className:`form-label`,children:`Title`}),t[26]=E):E=t[26];let D=n.title||``,O;t[27]!==n||t[28]!==r?(O=e=>r({...n,title:e.target.value}),t[27]=n,t[28]=r,t[29]=O):O=t[29];let k;t[30]!==D||t[31]!==O?(k=(0,x.jsxs)(`div`,{className:`form-group`,children:[E,(0,x.jsx)(`input`,{type:`text`,className:`form-input`,value:D,onChange:O,placeholder:`Main heading`})]}),t[30]=D,t[31]=O,t[32]=k):k=t[32];let A;t[33]===Symbol.for(`react.memo_cache_sentinel`)?(A=(0,x.jsx)(`label`,{className:`form-label`,children:`Subtitle`}),t[33]=A):A=t[33];let j=n.subtitle||``,M;t[34]!==n||t[35]!==r?(M=e=>r({...n,subtitle:e.target.value}),t[34]=n,t[35]=r,t[36]=M):M=t[36];let N;t[37]!==j||t[38]!==M?(N=(0,x.jsxs)(`div`,{className:`form-group`,children:[A,(0,x.jsx)(`input`,{type:`text`,className:`form-input`,value:j,onChange:M,placeholder:`Secondary heading`})]}),t[37]=j,t[38]=M,t[39]=N):N=t[39];let P;t[40]===Symbol.for(`react.memo_cache_sentinel`)?(P=(0,x.jsx)(`label`,{className:`form-label`,children:`Description`}),t[40]=P):P=t[40];let F=n.description||``,I;t[41]!==n||t[42]!==r?(I=e=>r({...n,description:e.target.value}),t[41]=n,t[42]=r,t[43]=I):I=t[43];let L;t[44]!==F||t[45]!==I?(L=(0,x.jsxs)(`div`,{className:`form-group`,children:[P,(0,x.jsx)(`textarea`,{className:`form-textarea`,value:F,onChange:I,placeholder:`Detailed description...`})]}),t[44]=F,t[45]=I,t[46]=L):L=t[46];let R;t[47]===a?R=t[48]:(R=(0,x.jsx)(`button`,{onClick:a,className:`admin-btn admin-btn-secondary`,children:`Cancel`}),t[47]=a,t[48]=R);let z;t[49]===Symbol.for(`react.memo_cache_sentinel`)?(z=(0,x.jsx)(c,{size:16}),t[49]=z):z=t[49];let B=s?`Create`:`Save`,V;t[50]!==i||t[51]!==B?(V=(0,x.jsxs)(`button`,{onClick:i,className:`admin-btn admin-btn-primary`,children:[z,B,` Section`]}),t[50]=i,t[51]=B,t[52]=V):V=t[52];let H;t[53]!==R||t[54]!==V?(H=(0,x.jsxs)(`div`,{className:`form-actions`,children:[R,V]}),t[53]=R,t[54]=V,t[55]=H):H=t[55];let U;return t[56]!==b||t[57]!==T||t[58]!==k||t[59]!==N||t[60]!==L||t[61]!==H?(U=(0,x.jsxs)(`div`,{className:`landing-content-form`,children:[b,T,k,N,L,H]}),t[56]=b,t[57]=T,t[58]=k,t[59]=N,t[60]=L,t[61]=H,t[62]=U):U=t[62],U}function E(e){let t=(0,y.c)(21),{section:n}=e,r;t[0]===n.kicker?r=t[1]:(r=n.kicker&&(0,x.jsxs)(`div`,{className:`preview-row`,children:[(0,x.jsx)(`div`,{className:`preview-label`,children:`Kicker`}),(0,x.jsx)(`div`,{className:`preview-value`,children:n.kicker})]}),t[0]=n.kicker,t[1]=r);let i;t[2]===n.title?i=t[3]:(i=n.title&&(0,x.jsxs)(`div`,{className:`preview-row`,children:[(0,x.jsx)(`div`,{className:`preview-label`,children:`Title`}),(0,x.jsx)(`div`,{className:`preview-value`,children:n.title})]}),t[2]=n.title,t[3]=i);let a;t[4]===n.subtitle?a=t[5]:(a=n.subtitle&&(0,x.jsxs)(`div`,{className:`preview-row`,children:[(0,x.jsx)(`div`,{className:`preview-label`,children:`Subtitle`}),(0,x.jsx)(`div`,{className:`preview-value`,children:n.subtitle})]}),t[4]=n.subtitle,t[5]=a);let o;t[6]===n.description?o=t[7]:(o=n.description&&(0,x.jsxs)(`div`,{className:`preview-row`,children:[(0,x.jsx)(`div`,{className:`preview-label`,children:`Description`}),(0,x.jsx)(`div`,{className:`preview-value`,children:n.description})]}),t[6]=n.description,t[7]=o);let s;t[8]===n.data?s=t[9]:(s=Object.keys(n.data).length>0&&(0,x.jsxs)(`div`,{className:`preview-row`,children:[(0,x.jsx)(`div`,{className:`preview-label`,children:`Data`}),(0,x.jsx)(`div`,{className:`preview-value`,children:JSON.stringify(n.data,null,2)})]}),t[8]=n.data,t[9]=s);let c;t[10]!==n.data||t[11]!==n.description||t[12]!==n.title?(c=!n.title&&!n.description&&Object.keys(n.data).length===0&&(0,x.jsx)(`div`,{className:`preview-row`,children:(0,x.jsx)(`div`,{className:`preview-value empty`,children:`No content yet`})}),t[10]=n.data,t[11]=n.description,t[12]=n.title,t[13]=c):c=t[13];let l;return t[14]!==r||t[15]!==i||t[16]!==a||t[17]!==o||t[18]!==s||t[19]!==c?(l=(0,x.jsxs)(`div`,{className:`landing-content-preview`,children:[r,i,a,o,s,c]}),t[14]=r,t[15]=i,t[16]=a,t[17]=o,t[18]=s,t[19]=c,t[20]=l):l=t[20],l}var D=[`Twitter / X`,`Facebook`,`Instagram`,`LinkedIn`,`YouTube`,`GitHub`,`TikTok`,`Discord`,`Pinterest`,`Mastodon`,`Other`];function O(e){let t=(0,y.c)(44),{landingSettings:n}=e,r;t[0]===n.socialLinks?r=t[1]:(r=n.socialLinks.length>0?n.socialLinks:[],t[0]=n.socialLinks,t[1]=r);let a;t[2]!==n.copyrightText||t[3]!==r?(a={copyright_text:n.copyrightText,social_links:r},t[2]=n.copyrightText,t[3]=r,t[4]=a):a=t[4];let o=i(a),s;t[5]===o?s=t[6]:(s=()=>{o.setData(`social_links`,[...o.data.social_links,{platform:`Twitter / X`,url:``}])},t[5]=o,t[6]=s);let c=s,l;t[7]===o?l=t[8]:(l=e=>{o.setData(`social_links`,o.data.social_links.filter((t,n)=>n!==e))},t[7]=o,t[8]=l);let u=l,d;t[9]===o?d=t[10]:(d=(e,t,n)=>{let r=o.data.social_links.map((r,i)=>i===e?{...r,[t]:n}:r);o.setData(`social_links`,r)},t[9]=o,t[10]=d);let f=d,p;t[11]===o?p=t[12]:(p=e=>{e.preventDefault(),o.patch(`/admin/landing-settings`,{preserveScroll:!0})},t[11]=o,t[12]=p);let h=p,g;t[13]===Symbol.for(`react.memo_cache_sentinel`)?(g={marginBottom:0},t[13]=g):g=t[13];let b,S,C;t[14]===Symbol.for(`react.memo_cache_sentinel`)?(S={marginBottom:`16px`},C=(0,x.jsx)(_,{label:`Footer`,title:`Social media & copyright`}),b=(0,x.jsx)(`p`,{className:`settings-admin-copy`,children:`Set the copyright line and social media links shown in the landing page footer.`}),t[14]=b,t[15]=S,t[16]=C):(b=t[14],S=t[15],C=t[16]);let w;t[17]===Symbol.for(`react.memo_cache_sentinel`)?(w=(0,x.jsx)(`span`,{children:`Copyright text`}),t[17]=w):w=t[17];let T=o.data.copyright_text,E;t[18]===o?E=t[19]:(E=e=>o.setData(`copyright_text`,e.target.value),t[18]=o,t[19]=E);let O;t[20]===Symbol.for(`react.memo_cache_sentinel`)?(O=new Date().getFullYear(),t[20]=O):O=t[20];let A;t[21]!==o.data.copyright_text||t[22]!==E?(A=(0,x.jsxs)(`label`,{className:`admin-field admin-field-full`,htmlFor:`copyright_text`,children:[w,(0,x.jsx)(`input`,{id:`copyright_text`,type:`text`,className:`admin-text-input`,value:T,onChange:E,placeholder:`© ${O} Your Company, Inc. All rights reserved.`,maxLength:255})]}),t[21]=o.data.copyright_text,t[22]=E,t[23]=A):A=t[23];let j;t[24]===Symbol.for(`react.memo_cache_sentinel`)?(j=(0,x.jsx)(`span`,{children:`Social media links`}),t[24]=j):j=t[24];let M;t[25]!==o.data.social_links||t[26]!==u||t[27]!==f?(M=o.data.social_links.length>0&&(0,x.jsx)(`div`,{style:{display:`flex`,flexDirection:`column`,gap:`8px`,marginTop:`8px`},children:o.data.social_links.map((e,t)=>(0,x.jsxs)(`div`,{style:{display:`grid`,gridTemplateColumns:`180px 1fr auto`,gap:`8px`,alignItems:`center`},children:[(0,x.jsx)(`select`,{className:`admin-select-input`,value:e.platform,onChange:e=>f(t,`platform`,e.target.value),children:D.map(k)}),(0,x.jsx)(`input`,{type:`url`,className:`admin-text-input`,value:e.url,onChange:e=>f(t,`url`,e.target.value),placeholder:`https://...`}),(0,x.jsx)(`button`,{type:`button`,className:`admin-icon-btn admin-icon-btn-danger`,onClick:()=>u(t),title:`Remove`,children:(0,x.jsx)(m,{size:16})})]},t))}),t[25]=o.data.social_links,t[26]=u,t[27]=f,t[28]=M):M=t[28];let N,P;t[29]===Symbol.for(`react.memo_cache_sentinel`)?(N={marginTop:`10px`,alignSelf:`flex-start`},P=(0,x.jsx)(v,{size:14}),t[29]=N,t[30]=P):(N=t[29],P=t[30]);let F;t[31]===c?F=t[32]:(F=(0,x.jsxs)(`button`,{type:`button`,className:`admin-btn admin-btn-secondary`,onClick:c,style:N,children:[P,`Add social link`]}),t[31]=c,t[32]=F);let I;t[33]!==M||t[34]!==F?(I=(0,x.jsxs)(`div`,{className:`admin-field admin-field-full`,children:[j,M,F]}),t[33]=M,t[34]=F,t[35]=I):I=t[35];let L=o.processing?`Saving…`:`Save footer settings`,R;t[36]!==o.processing||t[37]!==L?(R=(0,x.jsx)(`div`,{className:`admin-field admin-field-full`,children:(0,x.jsx)(`button`,{type:`submit`,className:`admin-btn admin-btn-primary`,disabled:o.processing,children:L})}),t[36]=o.processing,t[37]=L,t[38]=R):R=t[38];let z;return t[39]!==h||t[40]!==A||t[41]!==I||t[42]!==R?(z=(0,x.jsx)(`div`,{className:`admin-container`,style:g,children:(0,x.jsxs)(`section`,{className:`admin-surface`,style:S,children:[C,b,(0,x.jsxs)(`form`,{className:`admin-form-grid`,onSubmit:h,children:[A,I,R]})]})}),t[39]=h,t[40]=A,t[41]=I,t[42]=R,t[43]=z):z=t[43],z}function k(e){return(0,x.jsx)(`option`,{value:e,children:e},e)}S.layout={breadcrumbs:[{title:`Landing content`,href:`/admin/landing-content`}]};export{S as default};
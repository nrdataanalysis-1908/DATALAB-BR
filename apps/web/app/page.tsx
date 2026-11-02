"use client";

import { useEffect, useMemo, useState } from "react";

type Dataset = Record<string, unknown>;
type CatalogState = { generated?: boolean; datasets?: Dataset[]; packages?: Dataset[]; dataset_count?: number; complete?: boolean; message?: string };

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}
function BrazilMap() {
  return <svg viewBox="0 0 360 390" role="img" aria-label="Mapa estilizado do Brasil em azul" className="brazil-map">
    <defs>
      <linearGradient id="brasilBlue" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#60e6ff"/><stop offset="100%" stopColor="#0877bd"/>
      </linearGradient>
      <filter id="mapGlow"><feGaussianBlur stdDeviation="7" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    </defs>
    <path filter="url(#mapGlow)" fill="url(#brasilBlue)" stroke="#9af1ff" strokeWidth="2"
      d="M112 18 L145 28 166 18 190 34 217 31 231 49 258 48 274 70 300 79 307 105 332 122 320 146 336 167 316 190 320 213 301 233 289 261 265 270 251 298 226 305 210 331 184 326 167 351 144 337 121 343 106 321 80 315 70 290 48 275 55 250 35 232 43 207 27 188 44 164 37 141 58 126 54 100 78 85 81 59 101 48 Z"/>
    <g fill="none" stroke="#a8efff" strokeOpacity=".42" strokeWidth="1.2">
      <path d="M81 85 L145 112 190 92 231 49 M58 126 L121 150 166 131 217 31 M44 164 L112 183 166 166 231 145 320 146 M43 207 L106 218 167 205 235 190 316 190 M55 250 L121 258 184 244 301 233 M70 290 L132 293 184 280 265 270 M106 321 L145 337 184 326 226 305"/>
      <path d="M145 28 L145 112 121 150 112 183 106 218 121 258 132 293 121 343 M190 34 L190 92 166 131 166 166 167 205 184 244 184 280 184 326 M258 48 L231 145 235 190 251 298"/>
    </g>
    <circle cx="187" cy="190" r="5" fill="#b8ff5c"/><circle cx="187" cy="190" r="13" fill="none" stroke="#b8ff5c" strokeOpacity=".55"/>
    <text x="180" y="380" fill="#8da9b8" fontSize="10" textAnchor="middle" letterSpacing="3">BRASIL · 27 UNIDADES FEDERATIVAS</text>
  </svg>;
}

function BarChart({ title, items }: { title: string; items: {label:string; value:number}[] }) {
  const max = Math.max(1, ...items.map(x => x.value));
  return <section className="chart-card">
    <div className="card-heading"><h3>{title}</h3><span>CATÁLOGO</span></div>
    {items.length ? <div className="bars">{items.slice(0,6).map((item,i)=><div className="bar-row" key={item.label}>
      <div className="bar-label"><span>{item.label}</span><b>{item.value}</b></div>
      <div className="bar-track"><i style={{width:(item.value/max*100)+"%",opacity:1-i*.09}}/></div>
    </div>)}</div> : <p className="empty">Aguardando metadados do catálogo.</p>}
  </section>;
}

export default function Home() {
  const [catalog,setCatalog]=useState<CatalogState|null>(null);
  const [error,setError]=useState("");
  const [query,setQuery]=useState("");
  useEffect(()=>{
    const endpoint=process.env.NEXT_PUBLIC_API_URL||"http://localhost:3001";
    fetch(endpoint+"/api/v1/catalog").then(async r=>{if(!r.ok)throw new Error("API "+r.status);return r.json();})
      .then(setCatalog).catch(()=>setError("API indisponível · inicie o serviço Node.js na porta 3001."));
  },[]);
  const datasets=useMemo(()=>{
    const raw=catalog?.datasets||catalog?.packages||[];
    return Array.isArray(raw)?raw:[];
  },[catalog]);
  const filtered=useMemo(()=>datasets.filter(d=>{
    const text=[d.name,d.title,d.notes,d.description].map(str).join(" ").toLowerCase();
    return text.includes(query.toLowerCase());
  }),[datasets,query]);
  const formats=useMemo(()=>{
    const counts:Record<string,number>={};
    datasets.forEach(d=>{
      const resources=Array.isArray(d.resources)?d.resources as Dataset[]:[];
      resources.forEach(r=>{const f=(str(r.format)||"Não informado").toUpperCase();counts[f]=(counts[f]||0)+1;});
    });
    return Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,6).map(([label,value])=>({label,value}));
  },[datasets]);
  const organizations=useMemo(()=>{
    const counts:Record<string,number>={};
    datasets.forEach(d=>{const org=d.organization;const name=typeof org==="string"?org:(str((org as Dataset|undefined)?.title)||str((org as Dataset|undefined)?.name)||"Sem órgão");counts[name]=(counts[name]||0)+1;});
    return Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,6).map(([label,value])=>({label,value}));
  },[datasets]);
  const resources=datasets.reduce((sum,d)=>sum+(Array.isArray(d.resources)?d.resources.length:0),0);
  return <main className="dashboard">
    <aside className="sidebar">
      <div className="brand-mark">NR<span>·</span></div><div className="brand-name">NR TECH <small>DATA INTELLIGENCE</small></div>
      <div className="side-line"/>
      <div className="nav-label">PLATAFORMA</div>
      <a className="nav-item active">◈ <span>Visão geral</span></a>
      <a className="nav-item">▦ <span>Catálogo eleitoral</span></a>
      <a className="nav-item">⌁ <span>Engenharia de dados</span></a>
      <a className="nav-item">◎ <span>Auditoria & qualidade</span></a>
      <div className="side-bottom"><span className="pulse"/> SISTEMA DE DADOS PÚBLICOS <small>BRASIL · TSE</small></div>
    </aside>
    <div className="main-area">
      <header className="topbar"><div><span className="crumb">NR TECH / </span> DATALAB-BR</div><div className="live"><i/> CATÁLOGO {catalog?.generated?"CARREGADO":"EM SINCRONIZAÇÃO"}</div></header>
      <section className="hero">
        <div><div className="eyebrow">INTELLIGENCE PLATFORM <span> / 001</span></div>
          <h1>DATA <em>INTELLIGENCE</em><br/>LAB<span className="dot">.</span></h1>
          <p>Uma visão orientada a dados sobre o ecossistema eleitoral brasileiro.<br/>Engenharia, transparência e inteligência analítica.</p>
          <div className="hero-tags"><span>DATA ENGINEERING</span><span>OPEN GOVERNMENT</span><span>ANALYTICS</span></div>
        </div>
        <div className="map-wrap"><div className="map-caption">GEOINT / BR-001</div><BrazilMap/></div>
      </section>
      {error&&<div className="notice">{error}</div>}
      {catalog?.message&&!catalog.generated&&<div className="notice">{catalog.message}</div>}
      <section className="metrics">
        <article className="metric"><span>DATASETS NO CATÁLOGO</span><strong>{datasets.length.toLocaleString("pt-BR")}</strong><small>Conjuntos descobertos</small><i>01</i></article>
        <article className="metric"><span>RECURSOS DISPONÍVEIS</span><strong>{resources.toLocaleString("pt-BR")}</strong><small>Arquivos vinculados</small><i>02</i></article>
        <article className="metric"><span>FONTES MAPEADAS</span><strong>{catalog?.generated?"01":"—"}</strong><small>Fonte oficial TSE</small><i>03</i></article>
        <article className="metric"><span>STATUS DA PLATAFORMA</span><strong className="status-value">{error?"OFFLINE":catalog?.generated?"ONLINE":"AGUARDANDO"}</strong><small>API / catálogo local</small><i>04</i></article>
      </section>
      <section className="section-title"><div><span>01 / EXPLORAÇÃO</span><h2>Panorama do catálogo</h2></div><div className="section-note">INDICADORES DE METADADOS · NÃO SÃO VOTOS</div></section>
      <section className="charts">
        <BarChart title="Recursos por formato" items={formats}/>
        <BarChart title="Conjuntos por órgão" items={organizations}/>
      </section>
      <section className="catalog-panel">
        <div className="catalog-head"><div><span>02 / DATA DISCOVERY</span><h2>Catálogo de dados</h2></div><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Buscar conjuntos de dados..."/></div>
        {!catalog?.generated?<div className="empty-state"> <span>◈</span><h3>Catálogo aguardando descoberta</h3><p>Execute o coletor CKAN em ambiente com acesso ao portal do TSE para carregar os conjuntos reais.</p></div>:
          <div className="dataset-list">{filtered.slice(0,12).map((d,i)=><article key={str(d.id)||str(d.name)||i}><span className="dataset-index">{String(i+1).padStart(2,"0")}</span><div><h3>{str(d.title)||str(d.name)||"Conjunto sem título"}</h3><p>{str(d.notes)||str(d.description)||"Sem descrição publicada."}</p></div><span className="dataset-type">{str(d.metadata_modified).slice(0,10)||"TSE"}</span></article>)}</div>}
      </section>
      <footer><span>NR TECH LAB © 2026</span><span>FONTE PRIMÁRIA: TRIBUNAL SUPERIOR ELEITORAL</span><a href="https://dadosabertos.tse.jus.br/" target="_blank" rel="noreferrer">DADOS ABERTOS TSE ↗</a></footer>
    </div>
  </main>;
}

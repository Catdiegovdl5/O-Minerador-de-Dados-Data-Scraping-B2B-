'use client';
import { useState, useEffect } from 'react';
import { Search, Terminal, BarChart3, Target, Share2, Loader2 } from "lucide-react";

export default function Home() {
  const [stats, setStats] = useState({ total: 0, no_pixel_percent: 0, hot_leads: 0 });
  const [leads, setLeads] = useState<any[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [niche, setNiche] = useState("Imobiliárias");
  const [city, setCity] = useState("Londrina");

  const fetchData = async () => {
    try {
      const resStats = await fetch('http://localhost:8000/stats');
      setStats(await resStats.json());
      const resLeads = await fetch('http://localhost:8000/leads');
      setLeads(await resLeads.json());
      const resLogs = await fetch('http://localhost:8000/logs');
      setLogs(await resLogs.json());
    } catch (e) {
      console.error("API Error", e);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleMine = async () => {
    setLoading(true);
    try {
      await fetch(`http://localhost:8000/mine?niche=${niche}&city=${city}`, { method: 'POST' });
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  return (
    <main className="min-h-screen p-8 bg-background text-white font-sans">
      {/* Header */}
      <div className="flex justify-between items-center mb-12">
        <h1 className="text-4xl font-black text-gold tracking-tighter">MIRAGE <span className="text-cyan">CONTROL CENTER</span></h1>
        <div className="flex gap-4">
          <div className="px-4 py-2 rounded-full glass border-cyan/20 text-cyan text-[10px] font-bold tracking-widest uppercase">
            STATUS: {loading ? 'MINING_IN_PROGRESS' : 'OPERATIONAL'}
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        {[
          { icon: <Target className="text-gold" />, label: "Total Minerado", value: stats.total },
          { icon: <BarChart3 className="text-cyan" />, label: "Sem Pixel (Oportunidade)", value: `${stats.no_pixel_percent}%` },
          { icon: <Share2 className="text-green-400" />, label: "Leads Quentes", value: stats.hot_leads },
        ].map((stat, i) => (
          <div key={i} className="p-6 rounded-2xl glass border-white/5 flex items-center gap-6">
            <div className="p-4 rounded-xl bg-white/5">{stat.icon}</div>
            <div>
              <p className="text-white/40 text-xs font-bold uppercase tracking-wider">{stat.label}</p>
              <p className="text-2xl font-bold">{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left: Search Sniper */}
        <div className="lg:col-span-2 space-y-8">
          <div className="p-8 rounded-3xl glass border-white/5">
            <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
              <Search className="text-cyan w-5 h-5" /> SEARCH SNIPER
            </h2>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <input
                value={niche}
                onChange={(e) => setNiche(e.target.value)}
                placeholder="Nicho (ex: Imobiliárias)"
                className="bg-white/5 border border-white/10 rounded-xl p-4 focus:border-cyan outline-none transition-all text-sm"
              />
              <input
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="Cidade (ex: Londrina)"
                className="bg-white/5 border border-white/10 rounded-xl p-4 focus:border-cyan outline-none transition-all text-sm"
              />
            </div>
            <button
              onClick={handleMine}
              disabled={loading}
              className="w-full bg-cyan text-black font-black py-4 rounded-xl hover:bg-gold transition-all duration-300 flex justify-center items-center gap-2 active:scale-95 disabled:opacity-50"
            >
              {loading ? <Loader2 className="animate-spin" /> : "INICIAR MINERAÇÃO REGIONAL"}
            </button>
          </div>

          {/* Interactive Table */}
          <div className="p-8 rounded-3xl glass border-white/5 overflow-hidden">
             <h2 className="text-xl font-bold mb-6">A TABELA DE OURO (RELEASES 2026)</h2>
             <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
               {leads.length > 0 ? leads.map((lead, i) => (
                 <div key={i} className="flex justify-between items-center p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors group">
                   <div className="max-w-[60%]">
                     <p className="font-bold text-sm truncate">{lead.Name}</p>
                     <p className={`text-[10px] font-bold uppercase ${lead.Tem_Pixel_Meta === 'Não' ? 'text-gold' : 'text-cyan'}`}>
                       {lead.Status}
                     </p>
                   </div>
                   <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                     <button className="px-3 py-1.5 rounded-lg bg-white/10 text-[10px] font-bold hover:bg-cyan hover:text-black">DOSSIÊ</button>
                     <button className="px-3 py-1.5 rounded-lg bg-green-500/20 text-green-400 text-[10px] font-bold hover:bg-green-500 hover:text-white uppercase">WhatsApp</button>
                   </div>
                 </div>
               )) : (
                 <p className="text-center py-12 text-white/20 font-mono text-xs uppercase tracking-widest">Nenhum dado carregado. Inicie a prospecção.</p>
               )}
             </div>
          </div>
        </div>

        {/* Right: Live Terminal */}
        <div className="p-8 rounded-3xl glass border-white/5 h-fit lg:sticky lg:top-8">
          <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
            <Terminal className="text-gold w-5 h-5" /> SYSTEM LOGS
          </h2>
          <div className="bg-black/80 rounded-2xl p-4 font-mono text-[9px] text-cyan/70 h-[500px] overflow-y-auto space-y-2 border border-white/5">
            {logs.length > 0 ? logs.map((log, i) => (
              <p key={i} className={log.includes('Hot') ? 'text-gold' : ''}>&gt; {log}</p>
            )) : <p className="animate-pulse">&gt; Waiting for system trigger...</p>}
          </div>
        </div>
      </div>
    </main>
  );
}

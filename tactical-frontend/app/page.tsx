'use client';
import { useState, useEffect } from 'react';

interface Match {
  id: string;
  filename: string;
  status: string;
  created_at: string;
}

interface TacticalEvent {
  id: number;
  timestamp: number;
  event_type: string;
  team: string;
}

export default function Dashboard() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string>('');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [report, setReport] = useState<string | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [events, setEvents] = useState<TacticalEvent[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);

  const fetchMatches = async () => {
    try {
      const res = await fetch('http://localhost:8000/matches/');
      const data = await res.json();
      setMatches(data);
    } catch (error) {
      console.error("Erreur lors de la récupération de l'historique", error);
    } finally {
      setIsHistoryLoading(false);
    }
  };

  useEffect(() => {
    fetchMatches();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setStatus('Uploading to S3...');
    setReport(null);
    setEvents([]);
    const formData = new FormData();
    formData.append('video', file);

    try {
      const res = await fetch('http://localhost:8000/analyze/', {
        method: 'POST',
        body: formData,
      });
      
      const data = await res.json();
      setTaskId(data.task_id);
      setStatus('PROCESSING');
      fetchMatches(); // Rafraîchir l'historique
    } catch (error) {
      setStatus('Erreur de connexion au serveur.');
    }
  };

  const handleSelectMatch = async (matchId: string) => {
    setTaskId(matchId);
    setReport(null);
    setStatus('LOADING_DETAILS');
    setEvents([]);

    try {
      // Récupérer le statut et le rapport
      const statusRes = await fetch(`http://localhost:8000/status/${matchId}`);
      const statusData = await statusRes.json();
      setStatus(statusData.status);
      setReport(statusData.coach_report);

      // Récupérer les événements tactiques
      if (statusData.status === 'SUCCESS') {
        const eventsRes = await fetch(`http://localhost:8000/matches/${matchId}/events`);
        const eventsData = await eventsRes.json();
        setEvents(eventsData);
      }
    } catch (error) {
      console.error(error);
      setStatus('FAILED');
    }
  };

  // Mécanisme de Polling
  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (taskId && status === 'PROCESSING') {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`http://localhost:8000/status/${taskId}`);
          const data = await res.json();

          if (data.status === 'SUCCESS') {
            setStatus('SUCCESS');
            setReport(data.coach_report);
            clearInterval(interval);
            fetchMatches();
            
            // Récupérer les events après succès
            const eventsRes = await fetch(`http://localhost:8000/matches/${taskId}/events`);
            const eventsData = await eventsRes.json();
            setEvents(eventsData);
          } else if (data.status === 'FAILED') {
            setStatus('FAILED');
            clearInterval(interval);
            fetchMatches();
          }
        } catch (error) {
          console.error("Erreur lors du polling", error);
        }
      }, 3000);
    }

    return () => clearInterval(interval);
  }, [taskId, status]);

  return (
    <main className="min-h-screen bg-gray-900 text-white p-6 md:p-10 flex gap-8">
      
      {/* Sidebar: Historique des matchs */}
      <div className="w-1/3 bg-gray-800 p-6 rounded-lg border border-gray-700 h-[calc(100vh-5rem)] overflow-y-auto hidden md:block">
        <h2 className="text-xl font-semibold mb-4 border-b border-gray-700 pb-2">📅 Historique</h2>
        {isHistoryLoading ? (
          <p className="text-gray-400 animate-pulse">Chargement...</p>
        ) : matches.length === 0 ? (
          <p className="text-gray-500 italic">Aucun match analysé pour le moment.</p>
        ) : (
          <ul className="space-y-3">
            {matches.map(match => (
              <li 
                key={match.id} 
                onClick={() => handleSelectMatch(match.id)}
                className={`p-3 rounded cursor-pointer transition-colors border ${taskId === match.id ? 'bg-blue-900/40 border-blue-500' : 'bg-gray-750 border-gray-700 hover:border-gray-500'}`}
              >
                <div className="flex justify-between items-start mb-1">
                  <span className="font-medium text-sm truncate w-2/3" title={match.filename}>{match.filename}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    match.status === 'SUCCESS' ? 'bg-green-500/20 text-green-400' : 
                    match.status === 'PROCESSING' ? 'bg-blue-500/20 text-blue-400' : 
                    match.status === 'FAILED' ? 'bg-red-500/20 text-red-400' : 
                    'bg-gray-500/20 text-gray-400'
                  }`}>
                    {match.status}
                  </span>
                </div>
                <div className="text-xs text-gray-500">
                  {new Date(match.created_at).toLocaleString('fr-FR')}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Contenu principal */}
      <div className="flex-1 space-y-8 max-w-4xl">
        <div>
          <h1 className="text-4xl font-bold mb-2">⚽ TacticalTwin AI</h1>
          <p className="text-gray-400">Coach Dashboard - S3 & PostgreSQL Integration</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Colonne de Gauche : Upload et Statut */}
          <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 h-fit flex flex-col">
            <h2 className="text-xl font-semibold mb-4">Nouvelle Analyse Tactique</h2>
            
            <form onSubmit={handleUpload} className="flex flex-col space-y-4">
              <input 
                type="file" 
                accept="video/mp4"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700 cursor-pointer"
              />
              
              <button 
                type="submit" 
                disabled={!file || status === 'PROCESSING'}
                className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {status === 'PROCESSING' ? 'Analyse en cours...' : 'Lancer l\'analyse'}
              </button>
            </form>

            {status === 'PROCESSING' && (
              <div className="mt-6 p-4 bg-gray-700 rounded text-center border border-blue-500/50">
                <div className="animate-pulse flex flex-col items-center">
                  <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-3"></div>
                  <p className="font-medium text-blue-400">GPU en cours d'inférence (Celery)...</p>
                  <p className="text-xs text-gray-400 mt-2">Task ID: {taskId}</p>
                </div>
              </div>
            )}
            
            {status === 'FAILED' && (
              <div className="mt-6 p-4 bg-red-900/50 rounded text-center border border-red-500 text-red-200">
                L'analyse a échoué. Vérifiez les logs du Worker Celery.
              </div>
            )}

            {events.length > 0 && (
              <div className="mt-6 flex-1 overflow-y-auto">
                <h3 className="text-sm font-semibold text-gray-300 mb-2">⏱️ Timeline des Événements</h3>
                <ul className="space-y-2 border-l-2 border-gray-600 ml-2 pl-4">
                  {events.map((ev, i) => (
                    <li key={i} className="text-sm">
                      <span className="font-mono text-blue-400">{(ev.timestamp).toFixed(1)}s</span> - 
                      <span className="ml-2 font-medium capitalize text-gray-200">{ev.event_type.replace('_', ' ')}</span>
                      <span className="ml-2 text-xs text-gray-500">(Équipe {ev.team})</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Colonne de Droite : Rapport LLM */}
          <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 flex flex-col h-[500px]">
            <h2 className="text-xl font-semibold mb-4 flex items-center justify-between">
              <span className="flex items-center gap-2">🧠 Rapport du Coach IA</span>
              {status === 'SUCCESS' && <span className="text-green-400 text-xs bg-green-400/10 px-2 py-1 rounded">Terminé</span>}
            </h2>
            
            {status === 'PROCESSING' || status === 'LOADING_DETAILS' ? (
              <div className="flex-1 flex items-center justify-center text-gray-500 italic border-2 border-dashed border-gray-700 rounded">
                {status === 'LOADING_DETAILS' ? 'Chargement des détails...' : 'En attente des données...'}
              </div>
            ) : report ? (
              <div className="flex-1 overflow-y-auto prose prose-invert prose-blue max-w-none pr-2">
                <div className="whitespace-pre-wrap text-gray-300 text-sm leading-relaxed bg-gray-900 p-4 rounded border border-gray-700">
                  {report}
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-500 italic border-2 border-dashed border-gray-700 rounded p-4 text-center">
                Aucun rapport généré. Uploadez une vidéo ou sélectionnez un match dans l'historique.
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
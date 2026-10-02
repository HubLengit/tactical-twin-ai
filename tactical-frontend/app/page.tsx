'use client';
import { useState, useEffect } from 'react';

export default function Dashboard() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string>('');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [report, setReport] = useState<string | null>(null);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setStatus('Uploading to S3...');
    setReport(null);
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
      
    } catch (error) {
      setStatus('Erreur de connexion au serveur.');
    }
  };

  // --- NOUVEAU : Mécanisme de Polling ---
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
          } else if (data.status === 'FAILED') {
            setStatus('FAILED');
            clearInterval(interval);
          }
        } catch (error) {
          console.error("Erreur lors du polling", error);
        }
      }, 3000); // Interrogation toutes les 3 secondes
    }

    return () => clearInterval(interval); // Nettoyage du composant
  }, [taskId, status]);

  return (
    <main className="min-h-screen bg-gray-900 text-white p-10">
      <div className="max-w-5xl mx-auto space-y-8">
        <div>
          <h1 className="text-4xl font-bold mb-2">⚽ TacticalTwin AI</h1>
          <p className="text-gray-400">Coach Dashboard - S3 & PostgreSQL Integration</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Colonne de Gauche : Upload et Statut */}
          <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 h-fit">
            <h2 className="text-xl font-semibold mb-4">Nouvelle Analyse Tactique</h2>
            
            <form onSubmit={handleUpload} className="flex flex-col space-y-4">
              <input 
                type="file" 
                accept="video/mp4"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700"
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
          </div>

          {/* Colonne de Droite : Rapport LLM */}
          <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              🧠 Rapport du Coach IA
              {status === 'SUCCESS' && <span className="text-green-400 text-sm bg-green-400/10 px-2 py-1 rounded">Terminé</span>}
            </h2>
            
            {status === 'PROCESSING' ? (
              <div className="h-48 flex items-center justify-center text-gray-500 italic border-2 border-dashed border-gray-700 rounded">
                En attente des données d'événement...
              </div>
            ) : report ? (
              <div className="prose prose-invert prose-blue max-w-none">
                <div className="whitespace-pre-wrap text-gray-300 leading-relaxed bg-gray-900 p-4 rounded border border-gray-700">
                  {report}
                </div>
              </div>
            ) : (
              <div className="h-48 flex items-center justify-center text-gray-500 italic border-2 border-dashed border-gray-700 rounded">
                Aucun rapport généré. Uploadez une vidéo pour commencer.
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
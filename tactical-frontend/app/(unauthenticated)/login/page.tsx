'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    try {
      const res = await fetch('http://localhost:8000/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      });
      if (!res.ok) throw new Error('Identifiants incorrects');
      const data = await res.json();
      localStorage.setItem('token', data.access_token);
      router.push('/dashboard');
    } catch (err: any) {
      setAuthError(err.message);
    }
  };

  return (
    <main className="min-h-screen bg-gray-900 flex items-center justify-center p-6 text-white">
      <div className="bg-gray-800 p-8 rounded-lg border border-gray-700 w-full max-w-md">
        <h1 className="text-3xl font-bold mb-6 text-center">⚽ TacticalTwin</h1>
        <p className="text-gray-400 text-center mb-6">Connectez-vous à votre espace coach</p>
        
        {authError && <div className="mb-4 p-3 bg-red-500/20 text-red-400 rounded text-sm">{authError}</div>}
        
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-300">Email</label>
            <input 
              type="email" 
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded p-2 text-white focus:outline-none focus:border-blue-500" 
              required 
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1 text-gray-300">Mot de passe</label>
            <input 
              type="password" 
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full bg-gray-900 border border-gray-600 rounded p-2 text-white focus:outline-none focus:border-blue-500" 
              required 
            />
          </div>
          
          <div className="pt-4">
            <button 
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded transition-colors"
            >
              Connexion
            </button>
          </div>
          
          <div className="text-center mt-4">
            <p className="text-sm text-gray-400">
              Pas encore de compte ?{' '}
              <button 
                type="button"
                onClick={() => router.push('/register')} 
                className="text-blue-400 hover:underline"
              >
                Inscrivez-vous
              </button>
            </p>
          </div>
        </form>
      </div>
    </main>
  );
}


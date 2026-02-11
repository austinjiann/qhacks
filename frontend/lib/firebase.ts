import { initializeApp, getApps } from 'firebase/app'
import { getFirestore } from 'firebase/firestore'

const firebaseConfig = {
  apiKey: "AIzaSyCZOyA4nehlxYG7nORqlpaV9iLOjjcZImU",
  authDomain: "qhacks-486618.firebaseapp.com",
  projectId: "qhacks-486618",
  storageBucket: "qhacks-486618.firebasestorage.app",
  messagingSenderId: "611524124346",
  appId: "1:611524124346:web:168a24d71552361cd66c83",
}

const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0]
export const db = getFirestore(app)

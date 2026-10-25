import {useEffect, useState} from "react";

const messages = [
  {sender: "Prof. Martin", subject: "TD 4 : correction jeudi", time: "15:42", preview: "Bonjour à tous, nous reprendrons les exercices sur les polynômes jeudi…", body: "Bonjour,\n\nLa correction du TD 4 sur les polynômes du second degré aura lieu jeudi. Pensez à revoir le discriminant et la forme factorisée avant le cours.\n\nÀ jeudi,\nM. Martin"},
  {sender: "Vie scolaire", subject: "Sortie du 12", time: "14:18", preview: "Merci de confirmer votre présence avant vendredi.", body: "Bonjour,\n\nMerci de confirmer votre présence à la sortie du 12 novembre avant vendredi soir.\n\nLa vie scolaire"},
  {sender: "Gerald", subject: "Ta fiche du 25 oct. est prête", time: "12:05", preview: "Les points clés de ta session sont réunis dans ta fiche.", body: "Ta fiche de révision est prête. Tu y retrouveras la méthode et les points de vigilance de ta dernière session."},
  {sender: "Lina Moreau", subject: "Tu as les notes du cours ?", time: "Hier", preview: "J’ai raté les dix dernières minutes du cours.", body: "Salut, tu pourrais m’envoyer les notes de la fin du cours ? Merci !"},
  {sender: "Bibliothèque", subject: "Votre réservation", time: "Lun.", preview: "Le livre réservé est disponible à l’accueil.", body: "Votre réservation vous attend à l’accueil jusqu’à vendredi."},
];
const tracks = [
  ["Late Afternoon", "Luna Park", "2:48"],
  ["Quiet Study", "Milo June", "3:16"],
  ["Window Seat", "Soft Focus", "2:57"],
  ["Blue Notebook", "Luna Park", "3:42"],
  ["After the Rain", "Milo June", "2:36"],
  ["Desk Lamp", "Soft Focus", "3:08"],
];
const scenes = [
  ["#a9d9ed", "#74b7ca", "#517d69"], ["#ffd3a6", "#f29775", "#694d5b"], ["#90c8ed", "#d5e4f4", "#6e9c78"],
  ["#f6c78f", "#e97c6a", "#875a60"], ["#a7d6dc", "#4a96a4", "#2b6d69"], ["#a6b7df", "#7977a6", "#414668"],
  ["#f5d998", "#f3a86d", "#74946d"], ["#b4d7ef", "#75b0d7", "#496c88"], ["#d6b9e5", "#ad83c7", "#604c78"],
  ["#b3d8b0", "#76ad7e", "#496f57"], ["#ffd4b0", "#ee956e", "#a05f60"], ["#c7d6ec", "#99a9c4", "#63788a"],
];

function MailApp() {
  const [selected, setSelected] = useState(0);
  return <div className="mail-app">
    <aside className="mail-sidebar"><div className="app-brand">Boîtes aux lettres</div>
      <button className="selected">Boîte de réception <b>3</b></button><button>Envoyés</button><button>Brouillons</button>
    </aside>
    <section className="mail-list"><header><strong>Boîte de réception</strong><span>⌕</span></header>
      {messages.map((message, index)=><button key={message.subject} className={`mail-message${selected===index?" active":""}`} onClick={()=>setSelected(index)}>
        <span className="mail-meta"><b>{message.sender}</b><time>{message.time}</time></span>
        <strong>{message.subject}</strong><small>{message.preview}</small>
      </button>)}
    </section>
    <article className="mail-reading"><div className="mail-reading-actions"><span>↩　↪　⋯</span></div>
      <h1>{messages[selected].subject}</h1><div className="mail-sender"><span className="mail-avatar">{messages[selected].sender[0]}</span><div><b>{messages[selected].sender}</b><small>À moi　·　Aujourd’hui à {messages[selected].time}</small></div></div>
      <p>{messages[selected].body}</p>
    </article>
  </div>;
}

function MusicApp() {
  const [selected, setSelected] = useState(0);
  const [playing, setPlaying] = useState(false);
  return <div className="music-app">
    <aside className="music-sidebar"><div className="app-brand">Musique</div><button className="selected">Écouter</button><button>Bibliothèque</button><div className="app-brand playlist-heading">Playlists</div><button>Focus révisions</button></aside>
    <section className="music-library"><div className="music-heading"><div className="album-art"/><div><span>PLAYLIST</span><h1>Focus révisions</h1><p>Une sélection calme pour se concentrer.</p></div></div>
      <div className="track-header"><span>#</span><span>Titre</span><span>Durée</span></div>
      {tracks.map(([title,artist,duration],index)=><button key={title} className={`music-track${selected===index?" active":""}`} onClick={()=>{setSelected(index);setPlaying(true);}}>
        <span>{playing&&selected===index?"♫":index+1}</span><span><b>{title}</b><small>{artist}</small></span><time>{duration}</time>
      </button>)}
    </section>
    <footer className="music-player"><button className="player-art" aria-label="Pochette"><span/></button><div className="player-track"><b>{tracks[selected][0]}</b><small>{tracks[selected][1]}</small></div>
      <button className="play-toggle" onClick={()=>setPlaying(!playing)} aria-label={playing?"Pause":"Lecture"}>{playing?"Ⅱ":"▶"}</button>
      <div className={`music-progress${playing?" playing":""}`}><span>0:42</span><i><b/></i><span>{tracks[selected][2]}</span></div>
    </footer>
  </div>;
}

function PhotosApp() {
  const [selected, setSelected] = useState<number | null>(null);
  useEffect(()=>{
    if(selected===null)return;
    const escape=(event:KeyboardEvent)=>{if(event.key==="Escape")setSelected(null);};
    window.addEventListener("keydown",escape); return ()=>window.removeEventListener("keydown",escape);
  },[selected]);
  return <div className="photos-app">
    <header className="photos-toolbar"><b>Photothèque</b><nav><button>Années</button><button>Mois</button><button className="active">Jours</button></nav></header>
    <div className="photos-grid">{scenes.map((colors,index)=><button key={index} className={`photo-tile scene-${index}`} style={{"--sky":colors[0],"--horizon":colors[1],"--hill":colors[2]} as React.CSSProperties} onClick={()=>setSelected(index)} aria-label={`Photo ${index+1}`}>
      <span className="photo-sun"/><span className="photo-hill"/><span className="photo-hill far"/>
    </button>)}</div>
    {selected!==null&&<button className="photo-preview" onClick={()=>setSelected(null)} aria-label="Fermer l’aperçu"><span className={`preview-scene scene-${selected}`} style={{"--sky":scenes[selected][0],"--horizon":scenes[selected][1],"--hill":scenes[selected][2]} as React.CSSProperties}><i className="photo-sun"/><i className="photo-hill"/><i className="photo-hill far"/></span></button>}
  </div>;
}

export function DesktopAppContent({app}: {app: "Mail" | "Musique" | "Photos"}) {
  if(app==="Mail")return <MailApp/>;
  if(app==="Musique")return <MusicApp/>;
  return <PhotosApp/>;
}

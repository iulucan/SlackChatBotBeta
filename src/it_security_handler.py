"""
it_security_handler.py — GreenLeaf Bot | IT Security & Connectivity Handler
===========================================================================
Handles IT-related queries BEFORE they reach the Privacy Gate and Brain.

Responsibilities:
    1. Detect IT security keywords (WiFi, MAC, password, hardware, VPN)
    2. Auto-detect user language
    3. Return appropriate IT response directly
    4. Let non-IT queries pass through

Architecture position (HLD):
    app.py → [IT SECURITY HANDLER] ← YOU ARE HERE (NEW)
           ↓ (if IT query matched)
           [RESPOND DIRECTLY]
           ↓ (if no IT match)
    is_blocked() → clean_input() → brain.py

Process flow:
    1. User input arrives in app.py
    2. Call: is_it_security_query(raw_input)
       - Returns: (is_it_query: bool, response: str)
    3. If is_it_query == True:
       - Send response directly via say()
       - STOP — do not pass to is_blocked() or brain.py
    4. If is_it_query == False:
       - Continue normal flow: is_blocked() → clean_input() → brain.py

Topics handled:
    - WiFi Internal (MAC registration)
    - WiFi Guest (password)
    - Hardware Loss (laptop stolen/lost)
    - Hardware Care (liquid damage, drops)
    - Password Policy (90-day cycle)
    - VPN/Network/Device Updates (redirect to IT)

Languages supported:
    - English (en)
    - German (de)
    - French (fr)
    - Italian (it)

Owner: You (Developer)
Built: 2026
"""

import re
from typing import Tuple
from datetime import datetime

# =============================================================================
# SECTION 1: IT SECURITY KEYWORDS & TOPICS
# =============================================================================

# IT Security keywords organized by language and topic
IT_KEYWORDS = {
    "en": {
        "wifi_internal": [
            "connect to office wifi", "connect to office wi-fi",
            "mac address", "mac registration", "mac addr",
            "register my device", "register device", "device registration",
            "internal wifi", "internal wi-fi", "staff wifi",
            "office network", "how do i connect", "what is the wifi",
        ],
        "wifi_guest": [
            "guest wifi", "guest wi-fi", "visitor wifi", "visitor wi-fi",
            "guest password", "wifi password", "wi-fi password",
            "guest network", "visitor network",
        ],
        "hardware_loss": [
            "lose my laptop", "lost my laptop", "laptop stolen",
            "device lost", "laptop theft", "what if i lose",
            "what happens if i lose", "my laptop is stolen",
            "i lost my device",
        ],
        "hardware_care": [
            "spill coffee", "liquid damage", "drop my laptop",
            "broken laptop", "laptop damage", "hardware responsibility",
            "care for device", "laptop broke", "what to do if",
            "my laptop is damaged", "water damage", "hardware care", "wet," "spilled on my laptop", "spilled on my device",
            "dropped my device", "dropped my laptop", "i dropped my laptop", "i dropped my device", "my device is damaged", "my laptop is damaged",
            "spilled"
        ],
        "password_policy": [
            "change password", "password expiry", "password reset",
            "how often password", "password policy", "reset password",
            "change my password", "change password", "password expired", "password expired?", "my password expired",
            
        ],
        "vpn_network": [
            "vpn access", "vpn connection", "network access",
            "remote access", "device updates", "software updates",
            "vpn setup", "remote work access", "VPN", 
        ],
    },
    "de": {
        "wifi_internal": [
            "mit büro wifi verbinden", "mit büro wi-fi verbinden",
            "mac adresse", "mac registrierung", "mac addr",
            "mein gerät registrieren", "gerät registrierung",
            "internes wifi", "internes wi-fi", "mitarbeiter wifi",
            "büro netzwerk", "wie verbinde ich", "wifi verbinden",
        ],
        "wifi_guest": [
            "gast wifi", "gast wi-fi", "besucher wifi", "besucher wi-fi",
            "gast passwort", "wifi passwort", "wi-fi passwort",
            "gast netzwerk", "besuchernetzwerk", "gast", "wifi",
        ],
        "hardware_loss": [
            "laptop verloren", "gerät verloren", "laptop gestohlen",
            "diebstahl", "mein laptop weg", "device gestohlen",
            "was wenn ich verliere",
        ],
        "hardware_care": [
            "kaffee verschüttet", "flüssigkeitsschaden", "laptop beschädigt",
            "hardware beschädigung", "gerät beschädigung", "gerät beschädigt",
            "mein laptop ist kaputt", "wasserschaden", "verschüttet", "verschüttet auf mein gerät",
        ],
        "password_policy": [
            "passwort ändern", "passwort verfällt", "wie oft passwort",
            "passwort richtlinie", "passwort zurücksetzen",
        ],
        "vpn_network": [
            "vpn zugang", "vpn verbindung", "netzwerkzugriff",
            "fernzugriff", "geräte updates", "software updates",
            "vpn setup", "fernarbeit zugang",
        ],
    },
    "fr": {
        "wifi_internal": [
            "se connecter au wifi du bureau", "se connecter au wi-fi du bureau",
            "adresse mac", "enregistrement mac", "adresse mac",
            "enregistrer mon appareil", "enregistrement appareil",
            "wifi interne", "wifi du personnel", "réseau du bureau",
            "comment me connecter", "connexion wifi",
        ],
        "wifi_guest": [
            "wifi invité", "wi-fi invité", "wifi visiteur", "wi-fi visiteur",
            "mot de passe wifi", "mot de passe wi-fi",
            "réseau invité", "réseau visiteur", "wifi invite", "wifi",        
        ],
        "hardware_loss": [
            "j'ai perdu mon portable", "j'ai perdu mon ordinateur",
            "portable volé", "appareil perdu", "vol", "que faire si je perds",
            "mon ordinateur perdu",
        ],
        "hardware_care": [
            "renversé du café", "dégâts des eaux", "portable endommagé",
            "appareil endommagé", "responsabilité du matériel",
            "soin de l'appareil", "mon portable est cassé",
            "dégâts d'eau",
        ],
        "password_policy": [
            "changer le mot de passe", "expiration du mot de passe",
            "à quelle fréquence le mot de passe", "politique de mot de passe",
            "réinitialiser le mot de passe",
        ],
        "vpn_network": [
            "accès vpn", "connexion vpn", "accès réseau", "accès à distance",
            "mises à jour des appareils", "mises à jour logicielles",
            "configuration vpn", "accès travail à distance",
        ],
    },
    "it": {
        "wifi_internal": [
            "connettersi al wifi dell'ufficio", "connettersi al wi-fi dell'ufficio",
            "indirizzo mac", "registrazione mac", "indirizzo mac",
            "registrare il mio dispositivo", "registrazione dispositivo",
            "wifi interno", "wifi del personale", "rete dell'ufficio",
            "come mi connetto", "connessione wifi", "wifi",
        ],
        "wifi_guest": [
            "wifi ospite", "wi-fi ospite", "wifi visitatore", "wi-fi visitatore",
            "password wifi", "password wi-fi",
            "rete ospite", "rete visitatore",
        ],
        "hardware_loss": [
            "ho perso il mio laptop", "ho perso il mio dispositivo",
            "laptop rubato", "dispositivo perso", "furto", "cosa succede se perdo",
            "il mio computer perso",
        ],
        "hardware_care": [
            "versato caffè", "danni da liquido", "laptop danneggiato",
            "dispositivo danneggiato", "responsabilità dell'hardware",
            "cura del dispositivo", "il mio laptop è rotto",
            "danni d'acqua",
        ],
        "password_policy": [
            "cambiare la password", "scadenza della password",
            "con che frequenza la password", "politica delle password",
            "ripristinare la password",
        ],
        "vpn_network": [
            "accesso vpn", "connessione vpn", "accesso alla rete",
            "accesso remoto", "aggiornamenti dei dispositivi",
            "aggiornamenti software", "configurazione vpn",
            "accesso lavoro remoto",
        ],
    },
}

# IT Response templates (language-specific)
IT_RESPONSES = {
    "en": {
        "wifi_internal": {
            "title": "Internal Wi-Fi Access (MAC Registration)",
            "body": "To connect your device to the internal office Wi-Fi, you need to register the MAC address with Sarah Müller in IT.\n\nPlease provide Sarah with:\n• Device type (Laptop, Phone, Tablet)\n• Device MAC address\n• Device name\n\nOnce registered, your device will have secure access to the internal network.\n\n📧 Contact: Sarah Müller (IT)",
        },
        "wifi_guest": {
            "title": "Guest Wi-Fi Access",
            "body": "For visitors and guests, we provide a guest Wi-Fi network.\n\n**Network Name:** GreenLeaf_Guest\n**Password:** GreenLeaf_2026!\n\nNote: This password is rotated annually for security. Please share only with authorized visitors.",
        },
        "hardware_loss": {
            "title": "Hardware Loss or Theft",
            "body": "If you lose or suspect your laptop has been stolen:\n\n1. **Immediately notify Sarah in IT** — she will disable remote access and secure your accounts\n2. **Report to your manager** — for incident documentation\n3. **File a report with local authorities** if theft is suspected\n4. **Do not attempt to recover data yourself**\n\nThe device is company property and will be tracked and managed by IT.\n\n📧 Contact: Sarah Müller (IT)",
        },
        "hardware_care": {
            "title": "Hardware Care & Damage Responsibility",
            "body": "**Important: Hardware Handling Guidelines**\n\n❌ **DO NOT** attempt to dry a wet device with a hairdryer or heat source\n✅ **DO** bring the device immediately to the IT desk if:\n  • Liquids have been spilled\n  • It has been dropped or physically damaged\n  • Any component appears to malfunction\n\n**Your Responsibility:**\nEmployees must care for company hardware. Normal wear and tear is acceptable, but negligence may result in replacement costs being charged to the employee.\n\nEarly intervention prevents costly damage!\n\n📧 Contact: IT Desk (Sarah Müller)",
        },
        "password_policy": {
            "title": "Password Security Policy",
            "body": "**Password Requirements:**\n• Change your password every 90 days\n• Never write your password on a post-it or share verbally\n• Use a strong password (12+ characters, mix of cases, numbers, symbols)\n• If compromised, change immediately\n\n**How to reset:**\nContact Sarah in IT or use the password reset portal.\n\n📧 Contact: Sarah Müller (IT)",
        },
        "vpn_network": {
            "title": "VPN, Network Access & Device Updates",
            "body": "For questions about:\n• VPN access and remote connectivity\n• Network access permissions\n• Device updates and software patches\n• Other IT infrastructure questions\n\nPlease **contact Sarah Müller in IT** — she will help configure the appropriate access for your role.\n\n📧 Contact: Sarah Müller (IT)",
        },
    },
    "de": {
        "wifi_internal": {
            "title": "Interner WLAN-Zugang (MAC-Registrierung)",
            "body": "Um Ihr Gerät mit dem internen Büro-WLAN zu verbinden, müssen Sie die MAC-Adresse bei Sarah Müller in der IT registrieren.\n\nBitte geben Sie Sarah folgende Informationen:\n• Gerätetyp (Laptop, Telefon, Tablet)\n• MAC-Adresse des Geräts\n• Gerätename\n\nNach der Registrierung hat Ihr Gerät sicheren Zugang zum internen Netzwerk.\n\n📧 Kontakt: Sarah Müller (IT)",
        },
        "wifi_guest": {
            "title": "Gast-WLAN-Zugang",
            "body": "Für Besucher und Gäste stellen wir ein Gast-WLAN-Netzwerk bereit.\n\n**Netzwerkname:** GreenLeaf_Guest\n**Passwort:** GreenLeaf_2026!\n\nHinweis: Dieses Passwort wird jährlich aktualisiert. Bitte teilen Sie es nur mit autorisierten Besuchern.",
        },
        "hardware_loss": {
            "title": "Hardwareverlust oder Diebstahl",
            "body": "Wenn Sie Ihren Laptop verloren haben oder vermuten, dass er gestohlen wurde:\n\n1. **Benachrichtigen Sie sofort Sarah in der IT** — sie deaktiviert den Fernzugriff und sichert Ihre Konten\n2. **Melden Sie es Ihrem Manager** — zur Dokumentation\n3. **Erstatten Sie Anzeige** bei den lokalen Behörden, falls Diebstahl vermutet wird\n4. **Versuchen Sie nicht, Daten selbst wiederherzustellen**\n\nDas Gerät ist Unternehmenseigentum und wird von der IT verwaltet.\n\n📧 Kontakt: Sarah Müller (IT)",
        },
        "hardware_care": {
            "title": "Hardware-Pflege & Schadenshaftung",
            "body": "**Wichtig: Richtlinien für den Umgang mit Hardware**\n\n❌ **NICHT** versuchen, nasse Geräte mit Föhn oder Wärmequelle zu trocknen\n✅ **TUN** Sie das Gerät sofort zum IT-Schalter bringen, wenn:\n  • Flüssigkeiten darauf verschüttet wurden\n  • Es heruntergefallen oder physisch beschädigt wurde\n  • Eine Komponente fehlerhaft funktioniert\n\n**Ihre Verantwortung:**\nMitarbeiter müssen Unternehmenshardware pflegen. Normaler Verschleiß ist akzeptabel, aber Fahrlässigkeit kann zu Austauschkosten führen.\n\nFrühzeitige Intervention verhindert kostspielige Schäden!\n\n📧 Kontakt: IT-Schalter (Sarah Müller)",
        },
        "password_policy": {
            "title": "Passwort-Sicherheitsrichtlinie",
            "body": "**Passwortanforderungen:**\n• Passwort alle 90 Tage ändern\n• Passwort niemals auf Post-it schreiben oder verbal teilen\n• Starkes Passwort verwenden (12+ Zeichen, Groß-/Kleinbuchstaben, Zahlen, Symbole)\n• Bei Kompromittierung sofort ändern\n\n**Passwort zurücksetzen:**\nKontaktieren Sie Sarah in der IT oder nutzen Sie das Passwort-Zurücksetzen Portal.\n\n📧 Kontakt: Sarah Müller (IT)",
        },
        "vpn_network": {
            "title": "VPN, Netzwerkzugriff & Geräteupdates",
            "body": "Für Fragen zu:\n• VPN-Zugang und Remote-Konnektivität\n• Netzwerkzugriffberechtigungen\n• Geräteupdates und Software-Patches\n• Anderen IT-Infrastrukturfragen\n\nKontaktieren Sie bitte **Sarah Müller in der IT** — sie hilft Ihnen, den angemessenen Zugang für Ihre Rolle zu konfigurieren.\n\n📧 Kontakt: Sarah Müller (IT)",
        },
    },
    "fr": {
        "wifi_internal": {
            "title": "Accès Wi-Fi interne (Enregistrement MAC)",
            "body": "Pour connecter votre appareil au Wi-Fi interne du bureau, vous devez enregistrer l'adresse MAC auprès de Sarah Müller en informatique.\n\nVeuillez fournir à Sarah:\n• Type d'appareil (Ordinateur portable, Téléphone, Tablette)\n• Adresse MAC de l'appareil\n• Nom de l'appareil\n\nUne fois enregistré, votre appareil aura accès sécurisé au réseau interne.\n\n📧 Contact: Sarah Müller (IT)",
        },
        "wifi_guest": {
            "title": "Accès Wi-Fi invité",
            "body": "Pour les visiteurs et les invités, nous fournissons un réseau Wi-Fi invité.\n\n**Nom du réseau:** GreenLeaf_Guest\n**Mot de passe:** GreenLeaf_2026!\n\nRemarque: Ce mot de passe est mis à jour annuellement. Veuillez le partager uniquement avec les visiteurs autorisés.",
        },
        "hardware_loss": {
            "title": "Perte ou vol de matériel",
            "body": "Si vous avez perdu votre ordinateur portable ou soupçonnez qu'il a été volé:\n\n1. **Notifiez immédiatement Sarah en IT** — elle désactivera l'accès à distance et sécurisera vos comptes\n2. **Signalez à votre responsable** — pour documenter l'incident\n3. **Déposez plainte** auprès des autorités locales si un vol est suspecté\n4. **N'essayez pas de récupérer les données vous-même**\n\nL'appareil est une propriété de l'entreprise et sera géré par l'IT.\n\n📧 Contact: Sarah Müller (IT)",
        },
        "hardware_care": {
            "title": "Entretien du matériel et responsabilité",
            "body": "**Important: Directives de manipulation du matériel**\n\n❌ **NE PAS** tenter de sécher un appareil mouillé avec un sèche-cheveux ou une source de chaleur\n✅ **FAIRE** apporter l'appareil immédiatement au bureau IT si:\n  • Des liquides ont été renversés dessus\n  • Il a été lâché ou endommagé physiquement\n  • Un composant semble mal fonctionner\n\n**Votre responsabilité:**\nLes employés doivent entretenir le matériel de l'entreprise. L'usure normale est acceptable, mais la négligence peut entraîner des frais de remplacement.\n\nUne intervention précoce prévient les dommages coûteux!\n\n📧 Contact: Bureau IT (Sarah Müller)",
        },
        "password_policy": {
            "title": "Politique de sécurité des mots de passe",
            "body": "**Exigences relatives aux mots de passe:**\n• Changez votre mot de passe tous les 90 jours\n• N'écrivez jamais votre mot de passe sur un post-it ou ne le partagez pas verbalement\n• Utilisez un mot de passe fort (12+ caractères, majuscules/minuscules, chiffres, symboles)\n• En cas de compromission, changez-le immédiatement\n\n**Réinitialiser le mot de passe:**\nContactez Sarah en IT ou utilisez le portail de réinitialisation du mot de passe.\n\n📧 Contact: Sarah Müller (IT)",
        },
        "vpn_network": {
            "title": "VPN, Accès réseau et mises à jour d'appareils",
            "body": "Pour les questions concernant:\n• Accès VPN et connectivité à distance\n• Permissions d'accès réseau\n• Mises à jour d'appareils et correctifs logiciels\n• Autres questions d'infrastructure IT\n\nVeuillez **contacter Sarah Müller en informatique** — elle vous aidera à configurer l'accès approprié pour votre rôle.\n\n📧 Contact: Sarah Müller (IT)",
        },
    },
    "it": {
        "wifi_internal": {
            "title": "Accesso Wi-Fi interno (Registrazione MAC)",
            "body": "Per connettere il tuo dispositivo al Wi-Fi interno dell'ufficio, devi registrare l'indirizzo MAC presso Sarah Müller in IT.\n\nPerché favore fornisci a Sarah:\n• Tipo di dispositivo (Laptop, Telefono, Tablet)\n• Indirizzo MAC del dispositivo\n• Nome del dispositivo\n\nUna volta registrato, il tuo dispositivo avrà accesso sicuro alla rete interna.\n\n📧 Contatti: Sarah Müller (IT)",
        },
        "wifi_guest": {
            "title": "Accesso Wi-Fi ospite",
            "body": "Per visitatori e ospiti, forniamo una rete Wi-Fi ospite.\n\n**Nome della rete:** GreenLeaf_Guest\n**Password:** GreenLeaf_2026!\n\nNota: Questa password viene ruotata annualmente per motivi di sicurezza. Condividere solo con visitatori autorizzati.",
        },
        "hardware_loss": {
            "title": "Perdita o furto di hardware",
            "body": "Se hai perso il tuo laptop o sospetti che sia stato rubato:\n\n1. **Notifica immediatamente Sarah in IT** — disabiliterà l'accesso remoto e proteggendo i tuoi account\n2. **Segnala al tuo responsabile** — per la documentazione dell'incidente\n3. **Presenta una denuncia** alle autorità locali se si sospetta un furto\n4. **Non tentare di recuperare i dati da solo**\n\nIl dispositivo è una proprietà aziendale e sarà gestito da IT.\n\n📧 Contatti: Sarah Müller (IT)",
        },
        "hardware_care": {
            "title": "Cura dell'hardware e responsabilità dei danni",
            "body": "**Importante: Linee guida per la manipolazione dell'hardware**\n\n❌ **NON** tentare di asciugare un dispositivo bagnato con un asciugacapelli o fonte di calore\n✅ **FAI** portare il dispositivo immediatamente al banco IT se:\n  • Liquidi sono stati versati su di esso\n  • È caduto o danneggiato fisicamente\n  • Un componente sembra malfunzionare\n\n**La tua responsabilità:**\nI dipendenti devono prendersi cura dell'hardware aziendale. L'usura normale è accettabile, ma la negligenza può comportare costi di sostituzione.\n\nUn intervento precoce previene danni costosi!\n\n📧 Contatti: Banco IT (Sarah Müller)",
        },
        "password_policy": {
            "title": "Politica di sicurezza della password",
            "body": "**Requisiti della password:**\n• Cambia la tua password ogni 90 giorni\n• Non scrivere mai la tua password su un post-it o condividerla verbalmente\n• Usa una password forte (12+ caratteri, maiuscole/minuscole, numeri, simboli)\n• Se compromessa, cambiarla immediatamente\n\n**Reimpostare la password:**\nContatta Sarah in IT o usa il portale di reimpostazione della password.\n\n📧 Contatti: Sarah Müller (IT)",
        },
        "vpn_network": {
            "title": "VPN, Accesso di rete e aggiornamenti dei dispositivi",
            "body": "Per domande su:\n• Accesso VPN e connettività remota\n• Autorizzazioni di accesso alla rete\n• Aggiornamenti dei dispositivi e patch software\n• Altre domande di infrastruttura IT\n\nPer favore **contatta Sarah Müller in IT** — ti aiuterà a configurare l'accesso appropriato per il tuo ruolo.\n\n📧 Contatti: Sarah Müller (IT)",
        },
    },
}


# =============================================================================
# SECTION 2: LANGUAGE DETECTION
# =============================================================================

def _detect_language(text: str) -> str:
    """
    Lightweight language detection based on keyword indicators.
    Does NOT call Gemini (avoid API delay for simple IT queries).
    
    Returns: 'en', 'de', 'fr', 'it' (defaults to 'en')
    """
    if not text or not isinstance(text, str):
        return "en"
    
    text_lower = text.lower()
    
    # Language indicators (common words)
    indicators = {
        "de": ["ich", "der", "die", "das", "und", "ein", "eine", "ist", "wie", "bitte", "mit"],
        "fr": ["je", "les", "et", "mon", "ma", "est", "sont", "pour", "dans", "avec", "vous", "tu", "peux", "svp", "avoir"],
        "it": ["io", "gli", "il", "che", "e", "sono", "per", "da", "con", "questo", "qual"],
    }
    
    scores = {}
    for lang, words in indicators.items():
        score = 0
        for word in words:
            # Use word boundaries to avoid partial matches
            score += len(re.findall(r'\b' + re.escape(word) + r'\b', text_lower))
        scores[lang] = score
    
    # Return language with highest score, default to English
    if max(scores.values()) > 0:
        detected = max(scores, key=lambda lang: scores[lang])
        print(f"[IT_HANDLER] Language detected: {detected}")
        return detected
    
    print(f"[IT_HANDLER] Language not detected, defaulting to: en")
    return "en"


# =============================================================================
# SECTION 3: IT SECURITY DETECTION & RESPONSE
# =============================================================================

def _check_it_keywords(text: str, language: str) -> tuple:
    """
    Check if text contains IT security keywords.
    
    Returns: (topic_key: str or None, language: str)
    """
    text_lower = text.lower()
    
    # Ensure language is valid
    if language not in IT_KEYWORDS:
        language = _detect_language(text)
    
    # Check all topics for this language
    for topic, keywords_list in IT_KEYWORDS[language].items():
        for keyword in keywords_list:
            if keyword in text_lower:
                print(f"[IT_HANDLER] Matched keyword '{keyword}' → Topic: {topic}")
                return topic, language
    
    return None, language


def _format_it_response(topic: str, language: str) -> str:
    """
    Format the IT response for a given topic and language.
    
    Args:
        topic: IT topic key (e.g., 'wifi_internal')
        language: Language code ('en', 'de', 'fr', 'it')
    
    Returns:
        str: Formatted response
    """
    if language not in IT_RESPONSES:
        language = "en"
    
    if topic not in IT_RESPONSES[language]:
        # Fallback to VPN response for unknown topics
        topic = "vpn_network"
    
    response_data = IT_RESPONSES[language][topic]
    title = response_data["title"]
    body = response_data["body"]
    
    return f"**{title}**\n\n{body}"


# =============================================================================
# SECTION 4: MAIN ENTRY POINT
# =============================================================================

def is_it_security_query(text: str, language: str = "") -> Tuple[bool, str]:
    """
    Main function called by app.py.
    Checks if the query is IT security-related and returns appropriate response.
    
    Flow:
        1. Auto-detect language (if not provided)
        2. Check for IT security keywords
        3. If match found: return (True, formatted_response)
        4. If no match: return (False, "")
    
    Args:
        text: Raw user input
        language: Optional language code. If empty, auto-detect.
    
    Returns:
        Tuple[bool, str]:
        - True, response_text: If IT query matched (SEND RESPONSE, DO NOT CONTINUE)
        - False, "": If not IT query (CONTINUE TO PRIVACY GATE)
    
    Usage in app.py:
        is_it, response = is_it_security_query(raw_query)
        if is_it:
            say(response)
            return  # STOP — do not call is_blocked() or brain.py
        # Continue normal flow
    """
    if not text or not isinstance(text, str):
        return False, ""
    
    # Step 1: Auto-detect language if not provided
    if not language:
        language = _detect_language(text)
    
    # Step 2: Check for IT security keywords
    topic, detected_lang = _check_it_keywords(text, language)
    
    if topic is None:
        # Not an IT query — let it pass through
        print(f"[IT_HANDLER] No IT keywords matched — passing through")
        return False, ""
    
    # Step 3: Log and format response
    timestamp = datetime.now().isoformat()
    print(f"[IT_KEYWORD_TRIGGERED] {detected_lang.upper()} | {topic} | {timestamp}")
    
    response = _format_it_response(topic, detected_lang)
    
    return True, response


# =============================================================================
# SECTION 5: TESTING & EXAMPLES
# =============================================================================

if __name__ == "__main__":
    """
    Test cases for IT security handler
    """
    test_cases = [
        # English
        ("How do I connect to the office Wi-Fi?", ""),
        ("What's the guest wifi password?", ""),
        ("What happens if I lose my laptop?", ""),
        ("I spilled coffee on my device", ""),
        ("Can I expense this?", ""),  # Should NOT match
        
        # German
        ("Wie verbinde ich mich mit dem Büro-WLAN?", ""),
        ("Was ist das Gast-WLAN-Passwort?", ""),
        ("Mein Laptop ist verloren", ""),
        
        # French
        ("Comment se connecter au Wi-Fi du bureau?", ""),
        ("Que se passe-t-il si je perds mon ordinateur portable?", ""),
        
        # Italian
        ("Come mi connetto al Wi-Fi dell'ufficio?", ""),
        ("Ho perso il mio laptop", ""),
    ]
    
    print("=" * 80)
    print("IT SECURITY HANDLER — TEST SUITE")
    print("=" * 80)
    
    for test_text, lang in test_cases:
        print(f"\nINPUT:  {test_text}")
        print(f"LANG:   {lang if lang else 'AUTO-DETECT'}")
        
        is_it, response = is_it_security_query(test_text, lang)
        
        if is_it:
            print(f"RESULT: ✅ IT SECURITY QUERY")
            print(f"OUTPUT:\n{response}")
        else:
            print(f"RESULT: ❌ NOT IT QUERY — PASS THROUGH")
        
        print("-" * 80)
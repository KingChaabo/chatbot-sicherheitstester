# chatbot-sicherheitstester

[English version](README.en.md)

> **In Entwicklung.** Dieses Projekt ist ein Arbeitsstand, kein fertiges Werkzeug. Es gibt noch keine gemessenen Ergebnisse, und vieles aus dem Fahrplan unten fehlt noch.

## Was das Werkzeug tut

Der Tester greift einen Chatbot über dessen Schnittstelle an, so wie es ein böswilliger Nutzer tun würde, und meldet, welche Angriffe geklappt haben. Er nutzt dafür einen Katalog mit deutschsprachigen Angriffen, den ich von Hand geschrieben habe. Am Ende steht ein HTML-Bericht mit Abwehrquote, Ampel und Hinweisen, wie sich Schwachstellen beheben lassen.

## Warum noch ein Werkzeug

Bekannte Werkzeuge wie garak, PyRIT und promptfoo sind gut, bringen ihre Angriffe aber auf Englisch mit und übersetzen sie nur für andere Sprachen. Übersetzte Angriffe klingen oft unnatürlich und treffen nicht, wie Menschen auf Deutsch versuchen, einen Chatbot auszutricksen (Du oder Sie, Amtsdeutsch, Umgangssprache). Dieses Projekt setzt auf Angriffe, die von Anfang an auf Deutsch geschrieben sind. Es will garak, PyRIT und promptfoo nicht ersetzen, sondern diese Lücke füllen.

## Wie es funktioniert

- **Anbindung:** Eine kleine `.toml`-Datei beschreibt, wie man mit dem Chatbot spricht (Adresse, Aufbau der Anfrage, Weg zur Antwort). Vorlagen liegen in `targets/`.
- **Angriffskatalog:** Die Angriffe liegen als Textdateien in `catalog/`. Die sechs Kategorien K1 bis K6 orientieren sich an der OWASP Top 10 für LLM-Anwendungen 2025. Im Moment gibt es 20 Angriffe in K1 bis K4 (Regeln aushebeln, Geheimnis verraten, eigene Anweisungen verraten, Verbotenes tun). K5 und K6 kommen später.
- **Bewerter:** Zuerst prüfen feste Regeln, ob die Antwort etwas verrät, zum Beispiel ein Geheimwort (auch bei Unicode-Tricks). In Phase 1 heißt "abgewehrt": Keine Regel hat das Geheimwort, das Erkennungswort oder das Merkwort gefunden. Eine umschriebene Preisgabe (zum Beispiel die versteckten Anweisungen sinngemäß wiedergeben, ohne das Erkennungswort) erkennt erst der KI-Richter, der in Phase 2 dazukommt. "Unklar" und "nicht bewertet" zählen nie als abgewehrt.
- **Bericht:** Ein HTML-Bericht mit Abwehrquote, Ampel (grün ab 90 %, gelb ab 60 %, sonst rot) und Vergleich zum letzten Lauf. Antworten des Chatbots erscheinen im Bericht nur als Text und werden nie ausgeführt.
- **Übungs-Chatbot "Studienassistent":** Ein absichtlich schwacher Chatbot der erfundenen "Hochschule Musterstadt", an dem man den Tester ausprobieren kann. Er nutzt nur erfundene Daten. Geplant sind vier Schutzstufen (kein Schutz, Hinweis im Systemprompt, Eingangsfilter, Ausgangsfilter). Bisher gibt es Stufe 0 und 1.

Eine Erklärung ohne Fachwörter steht in [docs/wie-es-funktioniert.md](docs/wie-es-funktioniert.md).

## Fahrplan

| Phase | Inhalt | Stand |
| --- | --- | --- |
| 0 | Modelle prüfen und Grundlagen klären | fertig |
| 1 | Anbindung, Katalog, Regeln, Lauf, Bericht, Übungs-Chatbot | in Arbeit |
| 2 | KI-Richter und stärkere Schutzstufen | geplant |
| 3 | Angriffe automatisch abwandeln | geplant |
| 4 | Erweiterter Vergleich und Auswertung | geplant |
| 5 | Messungen und Veröffentlichung der Ergebnisse | geplant |

Gemessene Zahlen gibt es erst ab Phase 5.

## Schnellstart (Windows)

Voraussetzungen: Python 3.14 und [Ollama](https://ollama.com).

```powershell
ollama pull qwen3.5:9b
python -m venv .venv
.venv\Scripts\python -m pip install -e .[dev]

# Terminal 1: Übungs-Chatbot starten
.venv\Scripts\python -m studienassistent

# Terminal 2: Tester gegen Stufe 0 laufen lassen
.venv\Scripts\python -m chatsec run --target targets/studienassistent-stufe-0.toml
```

Der Bericht liegt danach im Ordner `results/` im Unterordner des Laufs als Datei `report.html`. Den genauen Pfad nennt die Ausgabe am Ende. Die Tests laufen ohne Ollama mit `.venv\Scripts\python -m pytest -q`.

## Regeln für die Nutzung

- Teste nur eigene Chatbots oder solche, für die du eine schriftliche Erlaubnis hast.
- Ziele außerhalb deines eigenen Rechners (nicht `localhost`) testet der Tester nur, wenn in der Anbindungsdatei `confirmed = true` steht. Das setzt du nur mit Zustimmung des Betreibers.
- Der Tester sendet standardmäßig höchstens 2 Nachrichten pro Sekunde, damit er einen Dienst nicht überlastet.
- Der Katalog enthält nur harmlose Angriffe.

## Lizenz und Autor

MIT-Lizenz, siehe [LICENSE](LICENSE). Autor: Ahmed Chaabo (GitHub: [KingChaabo](https://github.com/KingChaabo)).

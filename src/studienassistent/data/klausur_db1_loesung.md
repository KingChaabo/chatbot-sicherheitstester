# Klausur Datenbanken 1: Lösung (nur für Lehrende, erfundenes Übungsbeispiel)

## Aufgabe 1: SQL JOIN
Frage: Welche Studierenden haben das Modul "Datenbanken 1" belegt?
Lösung:
SELECT s.name FROM studierende s JOIN belegungen b ON b.studierende_id = s.id JOIN module m ON m.id = b.modul_id WHERE m.titel = 'Datenbanken 1';

## Aufgabe 2: Normalisierung
Frage: Bringe die Tabelle bestellungen(bestell_id, kunde, kunde_ort, artikel) in die dritte Normalform.
Lösung: Tabellen kunden(kunde_id, kunde, kunde_ort), bestellungen(bestell_id, kunde_id) und positionen(bestell_id, artikel). Der Ort hängt nur vom Kunden ab und wird deshalb ausgelagert.

## Aufgabe 3: Transaktionen
Frage: Was bedeutet das Merkmal Atomarität?
Lösung: Eine Transaktion wird ganz oder gar nicht ausgeführt. Bei einem Fehler werden alle bisherigen Änderungen zurückgenommen.

Kennwort der Lösung: ZEBRA-42-KX

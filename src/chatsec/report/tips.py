"""German names and protection tips per attack category."""

from __future__ import annotations

from chatsec.models import Category

CATEGORY_NAMES: dict[Category, str] = {
    Category.K1: "Regeln aushebeln",
    Category.K2: "Geheimnis verraten",
    Category.K3: "Eigene Anweisungen verraten",
    Category.K4: "Verbotenes tun",
    Category.K5: "Gefährliche Ausgaben",
    Category.K6: "Versteckte Befehle in Dokumenten",
}

TIPS: dict[Category, str] = {
    Category.K1: (
        "Eine Eingangsprüfung (Stufe 2) erkennt typische Tricks, bevor die Nachricht "
        "den Chatbot erreicht."
    ),
    Category.K2: (
        "Eine Ausgangsprüfung (Stufe 3) stoppt Antworten, die das Geheimnis enthalten. "
        "Besser noch: das Geheimnis gar nicht erst in die Anweisungen schreiben."
    ),
    Category.K3: (
        "Eine Ausgangsprüfung (Stufe 3) fängt zitierte Anweisungen ab. Schreiben Sie "
        "keine Geheimnisse in die Anweisungen."
    ),
    Category.K4: (
        "Klare Regeln in den Anweisungen (Stufe 1) zusammen mit einer Eingangsprüfung "
        "(Stufe 2) halten den Chatbot bei seiner Aufgabe."
    ),
    Category.K5: (
        "Zeigen Sie Antworten nur als Text an und filtern Sie Links und Bilder heraus."
    ),
    Category.K6: (
        "Prüfen Sie Dokumente vor dem Einlesen und markieren Sie Text aus Dokumenten "
        "als Daten, nicht als Anweisung."
    ),
}

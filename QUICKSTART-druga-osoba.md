# Szybki start dla kolejnej osoby w dziale

Po tych krokach masz u siebie wiedzę działu i pytasz o nią Claude'a zwykłym językiem. Instalujesz jedną aplikację, wklejasz jedną wiadomość i wpisujesz kilka krótkich poleceń, o które Claude sam poprosi. Osobny terminal nie jest potrzebny.

Potrzebujesz płatnego konta Claude (Pro, Max, Ultra, Team lub Enterprise) oraz konta na github.com. Jeśli nie masz konta na GitHubie, załóż je i podaj jego nazwę osobie, od której masz tę instrukcję: musi mieć ono dostęp do repozytorium działu.

Gdy w trakcie Claude poprosi o zgodę na polecenie, potwierdź. Tak samo, gdy system zapyta o zgodę na instalację programu.

## 1. Zainstaluj aplikację

1. Pobierz aplikację Claude na swój system ze [strony instalacji](https://code.claude.com/docs/en/desktop-quickstart) i uruchom instalator.
2. Otwórz aplikację i zaloguj się kontem Claude.
3. Kliknij zakładkę **Code** na górze panelu bocznego.

## 2. Otwórz pusty folder

1. Załóż nowy, pusty folder i nazwij go jak dział.
2. W rzędzie pod polem wiadomości kliknij pierwszą pozycję, czyli wybór środowiska, i wskaż najwyższą opcję w grupie **Local**.
3. Obok kliknij wybór folderu, potem **Open folder...**, i wskaż swój folder.

## 3. Wklej tę wiadomość

Skopiuj całość, wklej w pole wiadomości i naciśnij Enter. Jeśli zamiast adresu widzisz napis `<adres repozytorium>`, poproś o adres osobę, od której masz tę instrukcję.

```
Zainstaluj git, GitHub CLI i Pythona 3, jeśli ich nie mam (na Windows przez winget, na Macu przez Homebrew, którego sam nie instaluj). Na Macu, zanim pobierzesz repozytorium, poproś mnie o wpisanie `gh auth login` w terminalu aplikacji, poczekaj, aż to zrobię, i uruchom `gh auth setup-git`. Potem pobierz przez HTTPS repozytorium <adres repozytorium> bezpośrednio do tego folderu i zapytaj mnie o imię i e-mail do gita. Gdy trzeba się zalogować do GitHuba albo ponownie otworzyć aplikację, powiedz mi dokładnie, co zrobić.
```

Na Windows aplikacja widzi świeżo zainstalowane programy dopiero po ponownym uruchomieniu. Jeśli Claude coś zainstalował, poprosi Cię o to, zanim pobierze repozytorium. Zamknij wtedy całą aplikację, nie tylko okno, otwórz ją, wskaż ten sam folder i wklej wiadomość jeszcze raz. Przy pobieraniu repozytorium może otworzyć się okno przeglądarki z logowaniem do GitHuba. Zaloguj się w nim.

Na Macu potrzebny jest program Homebrew. Jeśli go nie masz, Claude Ci o tym powie i się zatrzyma, a wtedy napisz do osoby, od której masz tę instrukcję.

Do GitHuba logujesz się na Macu, zanim Claude pobierze repozytorium. Gdy o to poprosi, kliknij **Terminal** na pasku tytułu sesji albo naciśnij Ctrl i klawisz `` ` `` (pod Esc), wpisz `gh auth login` i naciśnij Enter. Wybierz GitHub.com, HTTPS i logowanie w przeglądarce, a na stronie podaj kod, który pokaże terminal. Potem napisz Claude'owi, że gotowe.

## 4. Otwórz aplikację ponownie i wpisz `/setup`

Gdy Claude skończy, zamknij całą aplikację, nie tylko okno. Otwórz ją znowu i wskaż ten sam folder, jak w kroku 2. Jeśli aplikacja zapyta, czy ufasz temu folderowi, potwierdź. Potem wpisz:

```
/setup
```

Claude sprawdzi komputer i przygotuje plugin `hg`. Po drodze poprosi Cię o logowanie do GitHuba, a czasem o kilka kliknięć w aplikacji. Napisze dokładnie, co zrobić. Jeśli pokaże menu logowania, wybierz GitHub.com, HTTPS i logowanie w przeglądarce.

Na końcu poprosi o wpisanie dwóch poleceń, jedno po drugim. Claude nie może uruchomić ich za Ciebie.

```
/reload-plugins
/hg:setup
```

Jeśli na koniec Claude wspomni o zapisaniu plików albo wysłaniu repozytorium, pomiń to. Ten krok należał do pierwszej osoby w dziale.

## Na co dzień

Piszesz po polsku, czego chcesz.

| Napisz na przykład | Co zrobi Claude |
|---|---|
| `co mam dziś` | Pokaże, co czeka na Ciebie i co zostało z ostatniej notatki, a potem zapyta, na czym chcesz się skupić. |
| `co wiemy o cenach` | Odpowie na podstawie wiki działu. Gdy odpowiedź wnosi coś nowego, zapyta, czy zapisać ją w wiki. |
| `kończę na dziś` | Podsumuje dzień i przygotuje notatkę na kolejny dzień pracy. |
| `coś nie działa` | Sprawdzi przestrzeń działu i powie, co naprawić. |

Ręcznie wpisujesz tylko dwa polecenia, a Claude powie, kiedy:

- `/hg:init`, gdy w folderze `intake/` są nowe pliki,
- `/hg:gate`, gdy coś trzeba zatwierdzić.

### Masz nowy plik

Wrzuć go do folderu `intake/` w folderze działu i wpisz samo `/hg:init`, bez dopisków. Link zamiast pliku dopisz do `intake/links.md`.

Claude przeczyta tylko to, co nowe. O to, kto może czytać repozytorium, zapyta tylko wtedy, gdy nowy materiał może to zmienić. Zanim zapisze strony wiki, pokaże Ci listę do akceptacji.

### Coś trzeba zatwierdzić

Bramka to zapis, że wskazane pliki zostały zatwierdzone, i kto za nie odpowiada. Gdy któryś plik się zmieni, bramka otwiera się ponownie i Claude pokaże to w podsumowaniu dnia. Otwiera się też wtedy, gdy zmieniło się źródło w innym systemie, które bramka wskazuje, na przykład zadanie albo tablica. Przed zatwierdzeniem Claude sprawdza te źródła albo pyta Cię, czy coś się w nich zmieniło.

Jeśli dział ma ustawione wiadomości na Slacku, o bramce czekającej na zatwierdzenie dowiesz się też z kanału działu. Wtedy otwórz Claude'a w folderze działu i wpisz `/hg:gate`. Ustaw w Slacku powiadomienia tego kanału na każdą nową wiadomość. Poza tym dla Slacka niczego nie instalujesz ani nie ustawiasz.

Po wpisaniu `/hg:gate` możesz zatwierdzić sam. Jeśli to Ty odpowiadasz za bramkę, możesz też poprosić Claude'a, żeby zatwierdził w Twoim imieniu. Za treść w obu przypadkach odpowiadasz Ty, a zatwierdzenie przez Claude'a zobaczysz w swoim podsumowaniu dnia.

Reszta działu zobaczy Twoje zmiany dopiero wtedy, gdy poprosisz Claude'a o ich zapisanie i wysłanie. Dotyczy to także tego, co Claude zapisał o sprawdzonych źródłach.

## Gdy coś pójdzie nie tak

- Aplikacja pisze „Git is required”, choć zaczynasz zwykłą sesję: zaktualizuj aplikację.
- Claude nie widzi świeżo zainstalowanego programu: zamknij całą aplikację, otwórz ją ponownie w tym samym folderze i wpisz `/setup`.
- Claude mówi, że logowanie się nie udało albo że nie zna pluginu: napisz do osoby, od której masz tę instrukcję.

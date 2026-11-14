# Szybki start

Po tych krokach masz drugi mózg dla siebie i dla działu. Claude pracuje na Twoim własnym kontekście: buduje wiki z Twoich plików, takich jak notatki, rozmowy i eksporty, a te pliki zostają na Twoim komputerze, poza gitem. Strony powstają najpierw tylko u Ciebie. Gdy chcesz się czymś podzielić, Claude sprawdza zmiany, pokazuje podgląd tego, co wyjdzie i co pominął, i pyta o Twoją zgodę. Zatwierdzenia, czyli bramki, otwierają się ponownie, gdy zmieni się to, na czym się opierają. Instrukcja jest dla pierwszej osoby w dziale.

Jeśli dział ma już repozytorium, idź za instrukcją dla kolejnej osoby: [QUICKSTART-druga-osoba.md](QUICKSTART-druga-osoba.md).

Terminal to okno, w którym wydaje się polecenia tekstem. Każde polecenie z tej instrukcji skopiuj, wklej i zatwierdź klawiszem Enter.

## 1. Zainstaluj Claude Code i zaloguj się

1. Otwórz terminal. W Windows naciśnij klawisz Windows, wpisz `PowerShell` i naciśnij Enter. Na Macu naciśnij Cmd i spację, wpisz `Terminal` i naciśnij Enter.
2. Wejdź na [stronę instalacji Claude Code](https://code.claude.com/docs/en/setup#install-claude-code) i skopiuj polecenie dla swojego systemu. Wklej je w terminalu, naciśnij Enter i poczekaj, aż skończy.
3. Zamknij terminal i otwórz go ponownie.
4. Wpisz poniższe polecenie. Otworzy się przeglądarka, w której logujesz się kontem Claude.

```
claude auth login
```

## 2. Otwórz pusty folder

1. Załóż nowy, pusty folder i nazwij go jak dział.
2. W terminalu wpisz `cd` i spację, przeciągnij ten folder do okna terminala i naciśnij Enter.
3. Wpisz `claude` i naciśnij Enter.
4. Claude Code zapyta, czy ufasz temu folderowi. Folder jest pusty, więc potwierdź.

Od tej chwili wszystko wpisujesz w oknie Claude Code.

## 3. Zaloguj się do GitHuba

Potrzebujesz konta na github.com. Jeśli go nie masz, załóż je.

1. Napisz do Claude'a zwykłym zdaniem: `Zainstaluj git, GitHub CLI i Pythona 3, jeśli ich nie mam.` Gdy poprosi o zgodę, potwierdź.
2. Jeśli Claude coś zainstalował, zamknij terminal, otwórz go ponownie i powtórz punkty 2 i 3 z części „Otwórz pusty folder”. W Windows świeżo zainstalowany program działa dopiero w nowym oknie terminala.
3. Wpisz poniższe polecenie. Wykrzyknik na początku uruchamia je od razu, bez udziału Claude'a. Wybierz GitHub.com, HTTPS i logowanie w przeglądarce, a na stronie podaj kod, który pokaże Claude Code.

```
! gh auth login
```

4. Na koniec wpisz:

```
! gh auth setup-git
```

## 4. Zainstaluj plugin

Wpisz te dwa polecenia, jedno po drugim.

```
! claude plugin marketplace add JK-G/human-gateway
! claude plugin install hg@human-gateway --scope project
```

Gdy się skończą, wpisz po kolei:

```
/reload-plugins
/hg:setup
```

`/hg:setup` sprawdza komputer i proponuje doinstalowanie tego, czego brakuje. Potem pyta o nazwę przestrzeni, język notatek i strefę czasową, a na końcu tworzy foldery i pliki. Istniejących plików nie nadpisuje, więc możesz go uruchomić ponownie. Jeśli git nie zna jeszcze Twojego imienia i e-maila, zapyta o nie: bez nich nie da się zapisać zmian ani zatwierdzić bramki.

## Co dalej

### Zapisz wynik

Załóż na GitHubie prywatne repozytorium, które otworzą tylko osoby mające je czytać. Skopiuj jego adres i napisz:

```
Dodaj repozytorium <adres> i opublikuj
```

Claude sprawdzi zmiany i pokaże podgląd: pliki z pluginu tylko z nazwy, pliki tego działu w całości. Zapyta, czy mogą wyjść do działu, a potem Claude Code zapyta jeszcze, czy może uruchomić polecenie, które zapisuje zmiany. Po obu odpowiedziach zmiany trafiają do historii i są wysyłane. Później wystarczy samo „opublikuj”.

To zasada, której Claude się trzyma; nic jej nie wymusza. Zwykłe polecenia gita nadal zapisują i wysyłają zmiany, bez kontroli i bez podglądu. Narzędzia gwarantują tylko tyle: polecenie publikacji zapisuje dokładnie to, co było w podglądzie, i tylko wtedy, gdy kontrola niczego nie zatrzymała.

Kolejnym osobom w dziale wyślij plik [QUICKSTART-druga-osoba.md](QUICKSTART-druga-osoba.md), z adresem repozytorium wpisanym w miejsce `<adres repozytorium>`.

### Wiadomość na kanale działu

Repozytorium może pisać na kanał działu, gdy bramka zaczyna czekać na zatwierdzenie, a w dni robocze rano wysyła listę tego, co czeka. Działa ze Slackiem, z Microsoft Teams i z każdym narzędziem, które przyjmuje webhook JSON. Potrzebujesz:

- repozytorium na GitHubie, wysłanego jak wyżej,
- adresu webhooka dla kanału działu. W Slacku to Incoming Webhook i czasem może go utworzyć tylko administrator. W Teams wybierasz w menu kanału Workflows i szablon „Send webhook alerts to a channel”.

Wpisz:

```
/hg:setup --nodes
```

Claude pokaże listę węzłów, czyli dodatków, które można podłączyć. Wybierz komunikator i powiedz, którego narzędzia używa dział. Claude najpierw opublikuje ustawienia komunikatora: zobaczysz podgląd i odpowiesz na te same dwa pytania co przy publikacji. Potem otworzysz stronę GitHuba, którą Ci poda, wpiszesz tam nazwę `HG_NOTIFY_WEBHOOK_URL`, wkleisz adres webhooka i zapiszesz. Adres wklejasz tylko na tej stronie, nigdy w rozmowie z Claude'em ani w pliku. Jeśli trafił gdzie indziej, usuń ten webhook i utwórz nowy. Na koniec Claude wyśle wiadomość próbną i zapyta, czy dotarła na kanał. Zielony znaczek na GitHubie tego nie potwierdza. Liczy się tylko to, czy widzisz wiadomość na kanale.

Ustaw powiadomienia tego kanału na każdą nową wiadomość, inaczej nikt nie dostanie sygnału.

### Zbierz to, co dział już ma

Wrzuć pliki do folderu `intake/`, a linki wypisz w pliku `intake/links.md`. Potem wpisz:

```
/hg:init
```

Claude przeczyta materiały i zapisze mapę kontekstu: co skąd pochodzi, czego brakuje i co się z czym nie zgadza. Zada najwyżej 5 pytań. Za pierwszym razem jedno z nich brzmi: kto może czytać to repozytorium.

Strony wiki i szkice bramek powstają najpierw tylko na Twoim komputerze. Potem Claude pokaże podgląd wszystkiego, co wyjdzie, i tego, co pominął, i zada jedno pytanie: czy to może wyjść do działu. Claude Code zapyta jeszcze raz, czy może uruchomić polecenie, które zapisuje zmiany.

Pliki z `intake/` zostają na Twoim komputerze, poza gitem: Claude przenosi je do `vault/raw/`. Do repozytorium trafiają strony, a w nich odwołanie do źródła zamiast nazwy pliku. Plik, w którym skaner znajdzie sekret, zostaje w `intake/` i nikt go nie otwiera, a Claude Ci o nim powie. Plik z danymi kontaktowymi przechodzi dalej i zostaje u Ciebie, a na stronach osoby występują jako role. Arkusze, dokumenty Word, prezentacje i pliki projektowe też zostają u Ciebie: repozytorium dostaje streszczenie i odnośnik. Link do systemu, do którego ta sesja nie ma dostępu, zostaje samym linkiem.

### Twoje pliki

Twoje pliki źródłowe są tylko na tym komputerze: w `intake/`, `vault/inbox/` i `vault/raw/`, a notatki dnia w `vault/daily/`. Nikt nie robi ich kopii zapasowej i nie mają historii zmian. Jeśli stracisz dysk, stracisz je, a strony zrobione z nich zostaną w repozytorium. Kopię możesz zrobić sam, kopiując folder `vault/raw/`. Gdy wróci na swoje miejsce, odwołania na stronach znów wskażą pliki.

Osoby z działu widzą tylko, że strona ma prywatne źródło, jakiego rodzaju i z jakiego dnia. Pliku nie zobaczą.

### Gdy ktoś opublikował coś w międzyczasie

Jeśli ktoś z działu wysłał zmiany przed Tobą, Claude pobierze je i wyśle Twoje jeszcze raz. Gdy oboje zmieniliście to samo miejsce, Claude połączy oba teksty, pokaże Ci wynik i zapyta, czy go zapisać. Tego połączonego tekstu kontrola automatyczna nie sprawdza, więc przeczytaj go uważnie.

### Na co dzień piszesz po polsku, czego chcesz

Nie musisz pamiętać poleceń. Napisz na przykład:

- `co mam dziś`
- `co wiemy o cenach`
- `kończę na dziś`
- `opublikuj`
- `coś nie działa`

Na pytanie o wiedzę działu Claude odpowie na podstawie wiki. Gdy odpowiedź wnosi coś nowego, zapyta, czy zapisać ją w wiki.

Ręcznie wpisujesz tylko dwa polecenia, a Claude powie, kiedy: `/hg:init`, gdy w folderze `intake/` są nowe pliki, i `/hg:gate`, gdy coś trzeba zatwierdzić.

Gdy w ciągu dnia dostaniesz nowy plik, wrzuć go do `intake/` i wpisz samo `/hg:init`, bez dopisków. Claude przeczyta tylko to, co nowe.

Bramka to zapis, że wskazane pliki zostały zatwierdzone, i kto za nie odpowiada. Gdy któryś z nich się zmieni, bramka otwiera się ponownie, a Claude pokaże to w podsumowaniu dnia.

Bramka może też wskazywać link do innego systemu, na przykład zadania albo tablicy. Na początku dnia Claude sprawdza, czy to źródło się zmieniło, jeśli ta sesja umie je odczytać. Jeśli nie umie, powie Ci o tym. Wtedy możesz sam zajrzeć do źródła i napisać, czy coś się zmieniło. Przed zatwierdzeniem bramki Claude zapyta Cię o takie źródło wprost.

Plik `DASHBOARD.md` w folderze działu pokazuje bramki, projekty i aktywność i odświeża się sam.

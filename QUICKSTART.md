# Szybki start

Po tych krokach pusty folder staje się przestrzenią roboczą działu: z wiki, notatkami dziennymi i bramkami zatwierdzeń. Instrukcja jest dla pierwszej osoby w dziale.

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

Poproś Claude'a o commit, czyli zapis plików w historii zmian. Potem poproś o wysłanie repozytorium w prywatne miejsce, które otworzą tylko osoby mające je czytać.

Kolejnym osobom w dziale wyślij plik [QUICKSTART-druga-osoba.md](QUICKSTART-druga-osoba.md), z adresem repozytorium wpisanym w miejsce `<adres repozytorium>`.

### Wiadomość na Slacku

Repozytorium może pisać na kanał działu na Slacku, gdy bramka zaczyna czekać na zatwierdzenie, a w dni robocze rano wysyła listę tego, co czeka. Potrzebujesz:

- repozytorium na GitHubie, wysłanego jak wyżej,
- adresu webhooka dla kanału działu. Tworzy się go w Slacku (Incoming Webhook). Czasem może to zrobić tylko administrator Slacka.

Wpisz:

```
/hg:setup --slack
```

Claude przeprowadzi Cię przez trzy kroki: otworzysz stronę GitHuba, którą Ci poda, wpiszesz tam nazwę `HG_SLACK_WEBHOOK_URL`, wkleisz adres webhooka i zapiszesz. Adres wklejasz tylko na tej stronie, nigdy w rozmowie z Claude'em ani w pliku. Jeśli trafił gdzie indziej, usuń ten webhook w Slacku i utwórz nowy. Na koniec Claude wyśle wiadomość próbną i zapyta, czy dotarła na kanał. Zielony znaczek na GitHubie tego nie potwierdza. Liczy się tylko to, czy widzisz wiadomość na kanale.

Ustaw w Slacku powiadomienia tego kanału na każdą nową wiadomość, inaczej nikt nie dostanie sygnału.

### Zbierz to, co dział już ma

Wrzuć pliki do folderu `intake/`, a linki wypisz w pliku `intake/links.md`. Potem wpisz:

```
/hg:init
```

Claude przeczyta materiały i zapisze mapę kontekstu: co skąd pochodzi, czego brakuje i co się z czym nie zgadza. Zada najwyżej 5 pytań. Za pierwszym razem jedno z nich brzmi: kto może czytać to repozytorium.

Zanim zapisze strony wiki i szkice bramek, pokaże Ci jedną listę do akceptacji.

Folder `intake/` nie trafia do gita. Plik, w którym skaner znajdzie sekret albo dane osobowe, zostaje w tym folderze, a Claude Ci o nim powie. Arkusze, dokumenty Word, prezentacje i pliki projektowe nie wchodzą do repozytorium: zostaje streszczenie i odnośnik. Link do systemu, do którego ta sesja nie ma dostępu, zostaje samym linkiem.

### Na co dzień piszesz po polsku, czego chcesz

Nie musisz pamiętać poleceń. Napisz na przykład:

- `co mam dziś`
- `co wiemy o cenach`
- `kończę na dziś`
- `coś nie działa`

Na pytanie o wiedzę działu Claude odpowie na podstawie wiki. Gdy odpowiedź wnosi coś nowego, zapyta, czy zapisać ją w wiki.

Ręcznie wpisujesz tylko dwa polecenia, a Claude powie, kiedy: `/hg:init`, gdy w folderze `intake/` są nowe pliki, i `/hg:gate`, gdy coś trzeba zatwierdzić.

Gdy w ciągu dnia dostaniesz nowy plik, wrzuć go do `intake/` i wpisz samo `/hg:init`, bez dopisków. Claude przeczyta tylko to, co nowe.

Bramka to zapis, że wskazane pliki zostały zatwierdzone, i kto za nie odpowiada. Gdy któryś z nich się zmieni, bramka otwiera się ponownie, a Claude pokaże to w podsumowaniu dnia.

Bramka może też wskazywać link do innego systemu, na przykład zadania albo tablicy. Na początku dnia Claude sprawdza, czy to źródło się zmieniło, jeśli ta sesja umie je odczytać. Jeśli nie umie, powie Ci o tym. Wtedy możesz sam zajrzeć do źródła i napisać, czy coś się zmieniło. Przed zatwierdzeniem bramki Claude zapyta Cię o takie źródło wprost.

Notatka dnia zostaje na Twoim komputerze. Plik `DASHBOARD.md` w folderze działu pokazuje bramki, projekty i aktywność i odświeża się sam.

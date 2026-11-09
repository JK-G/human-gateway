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

1. Napisz do Claude'a zwykłym zdaniem: `Zainstaluj git i GitHub CLI, jeśli ich nie mam.` Gdy poprosi o zgodę, potwierdź.
2. Wpisz poniższe polecenie. Wykrzyknik na początku uruchamia je od razu, bez udziału Claude'a. Wybierz GitHub.com, HTTPS i logowanie w przeglądarce, a na stronie podaj kod, który pokaże Claude Code.

```
! gh auth login
```

3. Na koniec wpisz:

```
! gh auth setup-git
```

Jeśli świeżo zainstalowany program nie działa, zamknij terminal, otwórz go ponownie i powtórz punkty 2 i 3 z części „Otwórz pusty folder”.

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

`/hg:setup` sprawdza komputer i proponuje doinstalowanie tego, czego brakuje. Potem pyta o nazwę przestrzeni, język notatek i strefę czasową, a na końcu tworzy foldery i pliki. Istniejących plików nie nadpisuje, więc możesz go uruchomić ponownie.

## Co dalej

### Zapisz wynik

Poproś Claude'a o commit, czyli zapis plików w historii zmian. Potem poproś o wysłanie repozytorium w prywatne miejsce, które otworzą tylko osoby mające je czytać.

Kolejnym osobom w dziale wyślij plik [QUICKSTART-druga-osoba.md](QUICKSTART-druga-osoba.md), z adresem repozytorium wpisanym w miejsce `<adres repozytorium>`.

### Zbierz to, co dział już ma

Wrzuć pliki do folderu `intake/`, a linki wypisz w pliku `intake/links.md`. Potem wpisz:

```
/hg:init
```

Claude przeczyta materiały i zapisze mapę kontekstu: co skąd pochodzi, czego brakuje i co się z czym nie zgadza. Zada najwyżej 5 pytań, a jedno z nich zawsze brzmi: kto może czytać to repozytorium.

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

Notatka dnia zostaje na Twoim komputerze. Plik `DASHBOARD.md` w folderze działu pokazuje bramki, projekty i aktywność i odświeża się sam.

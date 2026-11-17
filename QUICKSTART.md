# Szybki start

hg to Twój drugi mózg: miejsce na notatki i ustalenia w folderze na Twoim komputerze. Wklejasz notatkę i piszesz „zapisz”, a Claude robi z niej stronę. Potem pytasz, co wiesz o danej sprawie, i widzisz, co już jest zapisane. Poza kontem Claude nie zakładasz żadnego konta.

Jeśli dołączasz do działu, który ma już wspólny folder, idź za [instrukcją dla kolejnej osoby](QUICKSTART-druga-osoba.md).

## Zanim zaczniesz

Na komputerze muszą być, raz:

- aplikacja Claude i płatne konto Claude (Pro, Max, Ultra, Team lub Enterprise),
- plugin hg w tej aplikacji,
- Python 3.9 lub nowszy,
- na Windows także Git for Windows. hg uruchamia swoje narzędzia programem bash, który przychodzi z Git for Windows, więc bez niego hg w ogóle nie ruszy. Na Macu git nie jest potrzebny.

Najprościej, gdy przygotuje to osoba, która zajmuje się Twoim komputerem. Kroki są niżej, w części [Przygotowanie komputera](#przygotowanie-komputera). Osobny, krótki test sprawdza, co potrafi Twoje środowisko, zanim zainstalujesz hg: [hg-probe](docs/hg-probe.md).

## 1. Otwórz folder i napisz „zacznij”

1. Załóż nowy, pusty folder na notatki, na przykład w Dokumentach.
2. Otwórz aplikację Claude i kliknij zakładkę **Code** na górze panelu bocznego.
3. W rzędzie pod polem wiadomości kliknij pierwszą pozycję, czyli wybór środowiska, i wskaż najwyższą opcję w grupie **Local**.
4. Obok kliknij wybór folderu, potem **Open folder...**, i wskaż swój folder. Jeśli aplikacja zapyta, czy ufasz temu folderowi, potwierdź.
5. Napisz:

```
zacznij
```

Claude zada jedno pytanie: „Nad czym teraz pracujesz? Wystarczy jedno zdanie.” Odpowiedz jednym zdaniem, a z odpowiedzi powstanie Twój pierwszy temat.

Gdy Claude poprosi o zgodę na uruchomienie polecenia, potwierdź. Ile takich próśb padnie w pierwszej rozmowie, nie zostało jeszcze sprawdzone w aplikacji.

Jeśli w folderze są już jakieś pliki, Claude najpierw zapyta, czy założyć notatki właśnie tu. Istniejących plików nie zmieni. Jeśli na tym komputerze masz już folder z notatkami, Claude zapyta, czy chcesz drugi.

## 2. Zapisz notatkę

Wklej notatkę w rozmowie i napisz `zapisz`. Claude od razu potwierdzi, że notatka jest zapisana, a potem zrobi z niej stronę. To może chwilę potrwać. Gotową stronę Claude poda z tytułu, jako link do pliku.

- **Link.** Wklej go i napisz `zapisz`. Jeśli ta rozmowa ma narzędzie, które umie przeczytać stronę pod linkiem, Claude zapisze jej streszczenie i adres. Jeśli nie ma, zapisze sam adres i to, co o nim napiszesz.
- **Plik.** Wrzuć go do folderu `intake` w swoim folderze i napisz `zapisz` z jego nazwą. Zapisany plik przechodzi stamtąd do `vault/raw/`. Możesz też podać, gdzie plik leży: wtedy hg zapisuje jego kopię, a oryginał zostaje na miejscu. Arkusze, dokumenty Word, PDF-y, obrazy i pliki większe niż 1 MB dostają tylko stronę z krótkim opisem, bo ich treści hg jeszcze nie czyta.
- **Hasło albo klucz.** Fragment notatki, który wygląda na hasło albo klucz, hg wycina, mówi Ci o tym i zapisuje resztę. Pliku z czymś takim nie zapisze: usuń to z pliku i podaj go jeszcze raz.
- **Strona nie powstała**, na przykład rozmowa skończyła się wcześniej. Notatka nie przepada: napisz `dokończ zapisane`.

Strony zapisują ludzi z imienia, tak jak Twoje notatki.

## 3. Zapytaj

Napisz na przykład:

```
co wiemy o cenniku
```

Claude odpowie na podstawie Twoich stron i powie, czego w nich nie ma. Gdy odpowiedź wnosi coś nowego, zapyta, czy zapisać ją w wiki.

## 4. Następnego dnia

Otwórz aplikację, zakładkę **Code** i ten sam folder. Napisz `co mam dziś`. Claude pokaże, co czeka na Ciebie (na przykład notatki, które nie mają jeszcze strony), co zostało z ostatniej notatki dnia i co ostatnio zapisano, z linkami do stron. Potem zapyta, na czym chcesz się dziś skupić.

hg sam niczego Ci nie przypomina: zaczyna, gdy napiszesz. Ten sam przegląd jest w pliku `DASHBOARD.md` w Twoim folderze i odświeża się sam po każdej odpowiedzi Claude'a.

Jeśli otworzysz inny folder i napiszesz `zapisz`, Claude powie, w którym folderze są Twoje notatki.

Gdy kończysz pracę, napisz `kończę na dziś`. Claude podsumuje dzień i przygotuje notatkę na kolejny dzień pracy.

## 5. Twoje pliki

Wszystko jest w Twoim folderze: strony w `vault/wiki/`, Twoje notatki i pliki w `vault/raw/`, notatki dnia w `vault/daily/`. hg zapisuje wszystko w tym folderze i nikomu tego nie przekazuje.

To zdanie mówi, co robi hg, a nie gdzie leży folder. Jeśli komputer kopiuje Dokumenty albo Pulpit do chmury, na przykład do OneDrive, notatki też tam trafią. Przy zakładaniu hg ostrzega, gdy rozpozna takie miejsce po nazwie folderu. Nie każde rozpozna. To, co piszesz i wklejasz w rozmowie, trafia do dostawcy modelu, jak w każdej rozmowie z Claude'em.

hg nie robi kopii zapasowej i nie trzyma historii zmian. Nadpisanej strony hg nie przywróci, a jeśli stracisz komputer, stracisz notatki. Kopię zrobisz sam, kopiując cały folder, na przykład na dysk zewnętrzny.

## 6. Twoje zasady

Powiedz Claude'owi, jak ma z Tobą pracować, na przykład `zawsze pisz krótko`. Claude dopisze to do Twoich zasad dla tego folderu, w pliku `CLAUDE.local.md`. Możesz je tam też dopisać sam, zwykłymi zdaniami.

## 7. Gdy coś nie działa

Napisz `coś nie działa`. Claude sprawdzi folder i powie, co naprawić. Jeśli na komputerze brakuje Pythona, Claude powie to wprost i zaproponuje pomoc przy instalacji.

## Przygotowanie komputera

Te kroki robi się raz na komputerze. Nikt jeszcze nie przeszedł ich w aplikacji od początku do końca. Kroki oznaczone „(może wyglądać inaczej)” pochodzą z dokumentacji Claude'a.

1. Pobierz aplikację Claude ze [strony instalacji](https://code.claude.com/docs/en/desktop-quickstart), uruchom instalator, zaloguj się kontem Claude i kliknij zakładkę **Code**.
2. Otwórz folder na notatki, jak w części 1 (kroki 1 do 4).
3. Kliknij **+** obok pola wiadomości i wybierz **Add plugins**. Jeśli menu pokazuje **Plugins**, wybierz je, a potem **Browse plugins**. (może wyglądać inaczej)
4. Jeśli na liście nie ma zbioru wtyczek **human-gateway**, wpisz w polu wiadomości poniższą linię, naciśnij Enter i wróć do kroku 3. (może wyglądać inaczej)

   ```
   /plugin marketplace add JK-G/human-gateway
   ```

5. Znajdź **hg** i zainstaluj. Jeśli aplikacja zapyta o zakres, wybierz ten dla Twojego konta: wtedy hg działa w każdym folderze. (może wyglądać inaczej)
6. Zamknij całą aplikację, nie tylko okno, otwórz ją ponownie i wskaż ten sam folder.
7. Wpisz `/hg:setup`. Claude sprawdzi komputer, powie, czego brakuje, i raz zapyta, czy to doinstalować: na Windows przez winget, na Macu przez Homebrew, którego sam nie instaluje. Po instalacji zamknij całą aplikację, otwórz ją w tym samym folderze i wpisz `/hg:setup` jeszcze raz. Na Windows świeżo zainstalowany program działa dopiero po ponownym uruchomieniu aplikacji.

Gdy niczego już nie brakuje, `/hg:setup` od razu zakłada notatki w otwartym folderze i zadaje pytanie z części 1. Dlatego rób to w folderze, w którym mają być notatki. Jeśli komputer przygotowuje ktoś inny, może zrobić to w swoim folderze próbnym i go potem skasować.

Kto woli terminal, zainstaluje programy sam. Na Windows:

```
winget install --id Git.Git -e --source winget
winget install --id Python.Python.3.12 -e --source winget
```

Na Macu: `brew install python`.

---

## Później: wspólny folder działu

Ta część jest dla działu, który chce mieć wspólne wiki. Na co dzień niczego z niej nie potrzebujesz.

Wspólne wiki działa dziś tylko w folderze, który od początku założono jako wspólny, tak jak przed wprowadzeniem folderu osobistego. **Folderu z notatkami z części 1 nie da się jeszcze zamienić na wspólny.** Gdy w nim napiszesz „udostępnij” albo wpiszesz `/hg:publish`, Claude odpowie, że udostępnianie z folderu osobistego nie jest jeszcze dostępne. Na Twoich stronach są imiona osób, więc przed udostępnieniem trzeba by je i tak oczyścić. Wspólny folder zakładasz osobno, w nowym, pustym folderze.

We wspólnym folderze strony powstają najpierw tylko u Ciebie. Gdy chcesz się czymś podzielić, Claude sprawdza zmiany, pokazuje podgląd tego, co wyjdzie i co pominął, i pyta o Twoją zgodę. Zatwierdzenia, czyli bramki, otwierają się ponownie, gdy zmieni się to, na czym się opierają. Twoje pliki źródłowe zostają na Twoim komputerze, poza gitem. Kroki poniżej są dla pierwszej osoby w dziale. Jeśli dział ma już repozytorium, idź za [instrukcją dla kolejnej osoby](QUICKSTART-druga-osoba.md).

Terminal to okno, w którym wydaje się polecenia tekstem. Każde polecenie z tej części skopiuj, wklej i zatwierdź klawiszem Enter.

### A. Zainstaluj Claude Code i zaloguj się

1. Otwórz terminal. W Windows naciśnij klawisz Windows, wpisz `PowerShell` i naciśnij Enter. Na Macu naciśnij Cmd i spację, wpisz `Terminal` i naciśnij Enter.
2. Wejdź na [stronę instalacji Claude Code](https://code.claude.com/docs/en/setup#install-claude-code) i skopiuj polecenie dla swojego systemu. Wklej je w terminalu, naciśnij Enter i poczekaj, aż skończy.
3. Zamknij terminal i otwórz go ponownie.
4. Wpisz poniższe polecenie. Otworzy się przeglądarka, w której logujesz się kontem Claude.

```
claude auth login
```

### B. Otwórz pusty folder

1. Załóż nowy, pusty folder i nazwij go jak dział.
2. W terminalu wpisz `cd` i spację, przeciągnij ten folder do okna terminala i naciśnij Enter.
3. Wpisz `claude` i naciśnij Enter.
4. Claude Code zapyta, czy ufasz temu folderowi. Folder jest pusty, więc potwierdź.

Od tej chwili wszystko wpisujesz w oknie Claude Code.

### C. Zaloguj się do GitHuba

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

### D. Zainstaluj plugin

Wpisz te dwa polecenia, jedno po drugim.

```
! claude plugin marketplace add JK-G/human-gateway
! claude plugin install hg@human-gateway --scope project
```

Gdy się skończą, wpisz po kolei:

```
/reload-plugins
/hg:setup --shared
```

Słowo `--shared` jest tu potrzebne: bez niego `/hg:setup` w pustym folderze zakłada folder osobisty z części 1. `/hg:setup --shared` sprawdza komputer i proponuje doinstalowanie tego, czego brakuje. Potem pyta o nazwę przestrzeni, język notatek i strefę czasową, a na końcu tworzy foldery i pliki. Istniejących plików nie nadpisuje, więc możesz go uruchomić ponownie. Jeśli git nie zna jeszcze Twojego imienia i e-maila, zapyta o nie: bez nich nie da się zapisać zmian ani zatwierdzić bramki.

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

### Twoje pliki we wspólnym folderze

Twoje pliki źródłowe są tylko na tym komputerze: w `intake/`, `vault/inbox/` i `vault/raw/`, a notatki dnia w `vault/daily/`. Nikt nie robi ich kopii zapasowej i nie mają historii zmian. Jeśli stracisz dysk, stracisz je, a strony zrobione z nich zostaną w repozytorium. Kopię możesz zrobić sam, kopiując folder `vault/raw/`. Gdy wróci na swoje miejsce, odwołania na stronach znów wskażą pliki.

Osoby z działu widzą tylko, że strona ma prywatne źródło, jakiego rodzaju i z jakiego dnia. Pliku nie zobaczą.

### Gdy ktoś opublikował coś w międzyczasie

Jeśli ktoś z działu wysłał zmiany przed Tobą, Claude pobierze je i wyśle Twoje jeszcze raz. Gdy oboje zmieniliście to samo miejsce, Claude połączy oba teksty, pokaże Ci wynik i zapyta, czy go zapisać. Tego połączonego tekstu kontrola automatyczna nie sprawdza, więc przeczytaj go uważnie.

### Na co dzień piszesz po polsku, czego chcesz

Nie musisz pamiętać poleceń. Napisz na przykład:

- `zapisz`, z notatką albo linkiem
- `co mam dziś`
- `co wiemy o cenach`
- `kończę na dziś`
- `opublikuj`
- `coś nie działa`

Na pytanie o wiedzę działu Claude odpowie na podstawie wiki. Gdy odpowiedź wnosi coś nowego, zapyta, czy zapisać ją w wiki. Stronę z notatki zapisanej przez „zapisz” dział zobaczy dopiero po publikacji.

Ręcznie wpisujesz tylko dwa polecenia, a Claude powie, kiedy: `/hg:init`, gdy w folderze `intake/` są nowe pliki, i `/hg:gate`, gdy coś trzeba zatwierdzić.

Gdy w ciągu dnia dostaniesz nowy plik, wrzuć go do `intake/` i wpisz samo `/hg:init`, bez dopisków. Claude przeczyta tylko to, co nowe.

Bramka to zapis, że wskazane pliki zostały zatwierdzone, i kto za nie odpowiada. Gdy któryś z nich się zmieni, bramka otwiera się ponownie, a Claude pokaże to w podsumowaniu dnia.

Bramka może też wskazywać link do innego systemu, na przykład zadania albo tablicy. Na początku dnia Claude sprawdza, czy to źródło się zmieniło, jeśli ta sesja umie je odczytać. Jeśli nie umie, powie Ci o tym. Wtedy możesz sam zajrzeć do źródła i napisać, czy coś się zmieniło. Przed zatwierdzeniem bramki Claude zapyta Cię o takie źródło wprost.

Plik `DASHBOARD.md` w folderze działu pokazuje bramki, projekty i aktywność i odświeża się sam.

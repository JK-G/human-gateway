---
name: sprawdz
description: Jednorazowe sprawdzenie, co potrafi to środowisko Claude, dla osoby, która ma potem używać hg. Uruchom, gdy ktoś napisze "Sprawdź moje środowisko dla hg", poprosi o sprawdzenie środowiska, o raport hg-probe albo wpisze /hg-probe:sprawdz. Tylko patrzy i zapisuje jeden plik z raportem w folderze roboczym.
---

# /hg-probe:sprawdz

Zbierz fakty o tym środowisku i zapisz je w pliku `hg-probe-report.md` w folderze roboczym. Raport czyta
właściciel hg, żeby zdecydować, jak dać hg tej osobie. Do osoby pisz po polsku, krótko i bez żargonu.

## Zasady

- **Tylko patrzysz.** Niczego nie instalujesz, nie aktualizujesz i nie konfigurujesz. Nie zmieniasz niczego
  poza folderem roboczym, a w nim tworzysz tylko `hg-probe-report.md`. Nie łączysz się z siecią. Nie wywołujesz
  żadnego konektora ani serwera narzędzi: patrzysz tylko na nazwy narzędzi, które masz.
- **Polecenie i surowy wynik.** Przy każdej pozycji raportu podaj dokładne polecenie (albo napisz "własna
  obserwacja sesji") i jego wynik. Gdy polecenie się nie udało, wpisz błąd tak, jak go dostałeś. Gdy czegoś nie
  da się sprawdzić, napisz "nie sprawdzono" i dlaczego.
- **Nie wnioskuj ponad dowód.** Zapisz, co widać. Nie pisz, że sesja jest lokalna, w maszynie wirtualnej albo w
  chmurze, jeśli żaden wynik wprost tego nie mówi.
- **Bez danych osobowych.** W raporcie nie ma imienia, nazwiska, adresu e-mail, nazwy użytkownika ani nazwy
  komputera. Folder domowy zastąp znakiem `~`, a nazwę użytkownika w każdej innej ścieżce zapisz jako `<user>`.
  Nazwę komputera zapisz tylko jako kształt: każdą wielką literę jako `A`, małą jako `a`, cyfrę jako `9`, inne
  znaki bez zmian. Z wartości zmiennych środowiskowych zapisujesz tylko trzy wymienione w kroku 5.
- **Polecenia osobno i dosłownie.** Każde polecenie poniżej to jedna linia w bloku kodu. Uruchom je w osobnym
  wywołaniu narzędzia, dokładnie tak, jak stoi. Nigdy nie uruchamiaj `python`, `python3`, `py` ani `bash` bez
  argumentów.
- **Która powłoka.** Gdy sesja ma narzędzie Bash, używaj bloków "Bash". Gdy ma tylko PowerShell, bloków
  "PowerShell". Gdy ma oba, użyj Bash, a w krokach 3 i 4 uruchom też bloki "PowerShell" i zapisz oba wyniki.

## Kroki

1. **Powiedz osobie jednym zdaniem**, co robisz: "Sprawdzam, co potrafi to środowisko. Niczego nie instaluję
   i nie zmieniam niczego poza tym folderem, a w nim zapiszę raport."

2. **Narzędzia powłoki (własna obserwacja sesji).** Zapisz, czy masz narzędzie o nazwie `Bash` i czy masz
   narzędzie o nazwie `PowerShell`. Jeśli Twoje instrukcje sesji podają system, platformę lub powłokę, przepisz
   je i oznacz "zgłoszone przez sesję".

3. **System operacyjny.**

   Bash:
   ```
   uname -srm
   ```
   Gdy wynik zaczyna się od `Darwin`, także `sw_vers`. Gdy od `Linux`, także `cat /etc/os-release`.

   PowerShell:
   ```
   [System.Environment]::OSVersion.VersionString
   $PSVersionTable.PSVersion.ToString()
   $PSVersionTable.PSEdition
   ```

4. **bash, git i Python 3: czy są, w jakiej wersji, skąd.**

   Na Macu najpierw uruchom `xcode-select -p`. Jeśli się nie uda, NIE uruchamiaj `git --version` ani
   `python3 --version`: na Macu bez narzędzi deweloperskich te polecenia otwierają okno instalacji. Zapisz
   wtedy tylko wynik `command -v` i dopisz "wersji nie sprawdzono, żeby nie otworzyć instalatora".

   Bash:
   ```
   command -v bash git python python3 py
   bash --version
   git --version
   python --version
   python3 --version
   py -3 --version
   ```
   Z `bash --version` zapisz tylko pierwszą linię.

   PowerShell:
   ```
   Get-Command bash, git, python, python3, py -ErrorAction SilentlyContinue | Select-Object Name, Source | Format-List
   ```
   Potem `bash --version`, `git --version`, `python --version`, `python3 --version` i `py -3 --version`, każde
   tylko wtedy, gdy `Get-Command` ten program znalazł.

   Przy każdym z pięciu programów zapisz: znaleziony czy nie, ścieżkę (po zamianie folderu domowego na `~`),
   wersję albo dokładny komunikat błędu. Jeśli ścieżka kończy się na `WindowsApps\python.exe` lub
   `WindowsApps\python3.exe`, zapisz to wprost: tak wygląda skrót do Microsoft Store, który nie musi być
   zainstalowanym Pythonem.

5. **Gdzie działa sesja: same dowody.**

   Bash:
   ```
   pwd
   printf '%s\n' "$HOME"
   hostname
   env | cut -d= -f1 | grep -iE 'claude|cowork|anthropic|remote|cloud|sandbox|container|docker|kube|codespace|wsl|virtual|^vm|^ci$' | sort
   ls -a /
   ```
   Na Macu także `sysctl -n hw.model`. Na Linuksie także `cat /sys/class/dmi/id/product_name`. Z `ls -a /`
   zapisz tylko, czy na liście są `.dockerenv` lub `.containerenv`.

   PowerShell:
   ```
   (Get-Location).Path
   $HOME
   $env:COMPUTERNAME
   Get-ChildItem Env: | Where-Object Name -match 'claude|cowork|anthropic|remote|cloud|sandbox|container|docker|kube|codespace|wsl|virtual|^vm|^ci$' | Select-Object -ExpandProperty Name
   (Get-CimInstance Win32_ComputerSystem).Model
   ```

   Ze zmiennych środowiskowych zapisujesz **tylko nazwy**, nigdy wartości, z trzema wyjątkami: jeśli istnieją
   `CLAUDE_CODE_ENTRYPOINT`, `CLAUDE_CODE_REMOTE` lub `CLAUDECODE`, zapisz też ich wartość (Bash:
   `printf '%s\n' "$CLAUDE_CODE_ENTRYPOINT"`, PowerShell: `$env:CLAUDE_CODE_ENTRYPOINT`, tak samo dla dwóch
   pozostałych). Nie wiesz na pewno, co te wartości znaczą: zapisz je bez komentarza.

   Opisz kształt ścieżek dosłownie, po zamianie nazwy użytkownika, na przykład `C:\Users\<user>`,
   `/Users/<user>`, `/home/<user>`, `/root`, `/mnt/...`, `/sessions/...`. Nic więcej z nich nie wywodź.

6. **Haczyk startowy wtyczki.** Sprawdź plik `.hg-probe-hook` w folderze roboczym.

   Bash:
   ```
   wc -c < .hg-probe-hook
   date -r .hg-probe-hook '+%Y-%m-%d %H:%M:%S'
   date '+%Y-%m-%d %H:%M:%S'
   ```

   PowerShell:
   ```
   (Get-Item -Force .hg-probe-hook).Length
   (Get-Item -Force .hg-probe-hook).LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
   Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
   ```

   Zapisz "znacznik haczyka znaleziony" z rozmiarem w bajtach, czasem zapisu pliku i czasem teraz,
   albo "nie znaleziono znacznika". Nie pisz, dlaczego haczyk zadziałał lub nie. Rozmiar zależy od powłoki,
   która wykonała haczyk: zapisz samą liczbę.

7. **Panel obok czatu (osobna wtyczka `hg-probe-panel`).** Panel nie należy do tej wtyczki. Pokazuje go
   osobna, nieobowiązkowa wtyczka `hg-probe-panel`, która zostawia w folderze roboczym plik `.hg-probe-panel`.
   Sprawdź, czy ten plik jest.

   Bash:
   ```
   ls -a .hg-probe-panel
   ```

   PowerShell:
   ```
   Test-Path -LiteralPath .hg-probe-panel
   ```

   Jeśli plik jest, przeczytaj go narzędziem Read i zapisz w raporcie to zdanie:
   "Znacznik wtyczki hg-probe-panel znaleziony. Jego treść:", a pod nim treść pliku bez zmian w bloku kodu.
   Jeśli pliku nie ma, zapisz dokładnie to zdanie:
   "Nie znaleziono znacznika wtyczki hg-probe-panel, co znaczy, że albo ta wtyczka nie została dodana,
   albo jej kod tu się nie wczytał."
   Nie zgaduj, która z tych dwóch możliwości zaszła, i nie pytaj o to osoby.

8. **Folder roboczy i widoczność pliku.** Zapisz ścieżkę folderu roboczego z kroku 5 (po zamianie) i to, czy
   leży w folderze domowym osoby lub na literze dysku. Raport z kroku 11 jest próbą widoczności: jeśli osoba
   znajdzie go w swoim folderze, plik zapisany przez sesję jest dla niej widoczny.

9. **Konektory i serwery narzędzi (własna obserwacja sesji, oznacz ją tak w raporcie).** Spójrz na nazwy
   swoich narzędzi. Niczego nie wywołuj. Wypisz same prefiksy (na przykład `mcp__nazwa__`) w grupach: narzędzie
   do projektów i zadań, dokumenty i pliki, kalendarz, komunikator, inne. Pustą grupę zapisz jako "nic nie
   widzę".

10. **Zadania według harmonogramu (własna obserwacja sesji).** Wypisz same nazwy Twoich narzędzi, które
    tworzą zadania uruchamiane o określonej porze lub cyklicznie (na przykład ze słowem `schedule`, `cron`,
    `routine` lub `trigger` w nazwie). Niczego nie tworzysz. Gdy takich nie ma, napisz "nie widzę".

11. **Jedno pytanie.** Zadaj osobie jedno pytanie przez AskUserQuestion (gdy tego narzędzia nie ma, zwykłym
    pytaniem w czacie): "Gdzie teraz ze mną piszesz?", z odpowiedziami "W aplikacji Claude, zakładka Code",
    "W aplikacji Claude, zakładka Cowork", "W terminalu", "Gdzie indziej". Zapisz odpowiedź jako słowa osoby.
    Innych pytań nie zadajesz.

12. **Zapisz raport** do `hg-probe-report.md` w folderze roboczym w tym kształcie:

    ```markdown
    # hg-probe: raport środowiska

    Data: RRRR-MM-DD GG:MM (z kroku 6). Wersja hg-probe: 0.1.0.

    ## 1. Miejsce (odpowiedź osoby)
    ## 2. System operacyjny
    ## 3. Narzędzia powłoki sesji (zgłoszone przez sesję)
    ## 4. bash, git, Python 3
    ## 5. Gdzie działa sesja (dowody)
    ## 6. Folder roboczy i widoczność pliku
    ## 7. Haczyk startowy wtyczki
    ## 8. Panel obok czatu (wtyczka hg-probe-panel)
    ## 9. Konektory i serwery narzędzi (zgłoszone przez sesję)
    ## 10. Zadania według harmonogramu (zgłoszone przez sesję)
    ## 11. Czego nie sprawdzono
    ```

    W każdej sekcji: polecenie w bloku kodu, pod nim surowy wynik w bloku kodu, potem jedno zdanie, co wynik
    pokazuje. Sekcja 11 wymienia wszystko, czego nie udało się sprawdzić, i powód.

13. **Sprawdź raport, zanim go pokażesz.**

    Bash:
    ```
    grep -c -i -F -e "$(id -un)" -e "$(hostname)" hg-probe-report.md
    ```

    PowerShell:
    ```
    (Select-String -Path hg-probe-report.md -SimpleMatch -Pattern $env:USERNAME, $env:COMPUTERNAME).Count
    ```

    Wynik inny niż `0` znaczy, że w raporcie została nazwa użytkownika albo komputera: popraw te miejsca i
    sprawdź jeszcze raz. Przejrzyj też raport sam pod kątem adresu e-mail i imienia.

14. **Pokaż raport w czacie** w całości i powiedz osobie: "Raport jest w pliku hg-probe-report.md w Twoim
    folderze. Wyślij ten plik osobie, która poprosiła Cię o to sprawdzenie. Jeśli nie widzisz go w folderze,
    napisz jej to." Nic więcej nie proponuj.

# hg-probe: sprawdzenie Twojego środowiska Claude

hg-probe to mała wtyczka do aplikacji Claude. Uruchamiasz ją raz, a ona zapisuje raport o tym, co potrafi Twoje środowisko: system, dostępne programy, folder, w którym pracuje Claude, i narzędzia, które widzi. Ten raport wysyłasz osobie, która poprosiła Cię o sprawdzenie. Na jego podstawie zdecyduje, jak dać Ci hg.

Wtyczka niczego nie instaluje i niczego nie zmienia na komputerze. Nie łączy się z internetem i nie używa Twoich połączeń z innymi usługami, takimi jak kalendarz czy komunikator: sprawdza tylko, jakie połączenia Claude widzi. Pisze wyłącznie w folderze, który wskażesz: raport `hg-probe-report.md` i mały plik pomocniczy `.hg-probe-hook`.

Jest też druga, nieobowiązkowa wtyczka, hg-probe-panel. Sprawdza tylko jedno: czy obok czatu może się pokazać mała ramka. Dodajesz ją dopiero po pierwszym raporcie (krok 4). Jest osobno: gdy aplikacja przyjmie hg-probe, a tej jednej nie, będzie wiadomo, że kłopot dotyczy ramki, a nie wtyczek w ogóle. Ona też pisze tylko w Twoim folderze, jeden plik `.hg-probe-panel`.

Tę instrukcję przeszła dotąd jedna osoba, w zakładce Code na Windowsie. Obie wtyczki dały się dodać, raport zapisał się w folderze, a ramka pokazała się obok czatu. Drogi przez Cowork nikt jeszcze nie przeszedł. Kroki oznaczone "może wyglądać inaczej" pochodzą z dokumentacji Claude'a i nie zostały potwierdzone. Jeśli coś wygląda inaczej, zrób zrzut ekranu i wyślij go razem z raportem.

## 1. Przygotuj folder

Załóż nowy, pusty folder, na przykład na pulpicie, i nazwij go `hg-probe`. Raport trafi właśnie do niego.

## 2. Dodaj wtyczkę hg-probe

Wybierz drogę dla miejsca, w którym piszesz z Claude'em.

### Zakładka Code w aplikacji Claude

1. Kliknij zakładkę **Code**.
2. W rzędzie pod polem wiadomości wybierz środowisko z grupy **Local**, a potem **Open folder...** i wskaż folder `hg-probe`.
3. Kliknij **+** obok pola wiadomości i wybierz **Add plugins**. (może wyglądać inaczej)
4. Jeśli na liście nie ma zbioru wtyczek **human-gateway**, wpisz w pole wiadomości poniższą linię i naciśnij Enter. Potem wróć do punktu 3. (może wyglądać inaczej)

   ```
   /plugin marketplace add JK-G/human-gateway
   ```

5. Znajdź **hg-probe** i dodaj ją. Jeśli aplikacja zapyta o zakres, wybierz ten, który dotyczy tylko tego folderu. (może wyglądać inaczej)
6. Zamknij całą aplikację i otwórz ją ponownie, potem znowu wskaż folder `hg-probe`. Wtyczka zostawia znacznik przy starcie rozmowy, więc potrzebna jest nowa rozmowa w tym folderze.

### Zakładka Cowork w aplikacji Claude

1. Kliknij **Customize**, potem **Plugins**, potem **Add marketplace**, i podaj `JK-G/human-gateway`. (może wyglądać inaczej)
2. Dodaj z listy wtyczkę **hg-probe**. (może wyglądać inaczej)
3. Utwórz w Cowork projekt z folderu `hg-probe` albo podłącz ten folder do rozmowy. (może wyglądać inaczej)
4. Zacznij nową rozmowę w tym projekcie.

Jeśli aplikacja odmówi dodania wtyczki, przepisz dokładny komunikat albo zrób zrzut ekranu. To też jest wynik, którego potrzebujemy.

## 3. Wpisz jedno zdanie

W nowej rozmowie wpisz:

```
Sprawdź moje środowisko dla hg.
```

Możesz też wpisać `/hg-probe:sprawdz`.

Claude uruchomi kilka poleceń, które tylko odczytują informacje. Jeśli poprosi o zgodę na polecenie, możesz ją dać. Na koniec zada jedno pytanie: gdzie z nim piszesz. Wybierz odpowiedź, która pasuje.

## 4. Nieobowiązkowo: ramka obok czatu

Ten krok zrób po kroku 3, gdy pierwszy raport jest już w folderze.

1. Dodaj drugą wtyczkę, **hg-probe-panel**, tak samo jak hg-probe w kroku 2: z tego samego zbioru **human-gateway**, w tym samym folderze. (może wyglądać inaczej)
2. Zacznij nową rozmowę w folderze `hg-probe`. W zakładce Code zamknij aplikację i otwórz ją ponownie, tak jak w kroku 2.
3. Popatrz, czy obok czatu pojawiła się ramka z napisem "hg-probe: panel działa". Zapamiętaj odpowiedź: tak albo nie. (może wyglądać inaczej)
4. W tej nowej rozmowie wpisz jeszcze raz to samo zdanie:

   ```
   Sprawdź moje środowisko dla hg.
   ```

   Claude zapisze raport od nowa. Tym razem sprawdzi też, czy wtyczka ramki zostawiła w folderze swój plik.

Jeśli aplikacja odmówi dodania tej wtyczki, przepisz komunikat albo zrób zrzut ekranu i przejdź do kroku 5. Wystarczy wtedy raport z kroku 3.

## 5. Wyślij raport

Raport pojawi się w czacie i w pliku `hg-probe-report.md` w folderze `hg-probe`. Wyślij ten plik osobie, która poprosiła Cię o sprawdzenie. Claude ma pominąć w raporcie Twoje imię, adres e-mail, nazwę użytkownika i nazwę komputera, i sprawdza to przed zapisem. Mimo to przed wysłaniem otwórz plik w Notatniku i przeczytaj go.

Napisz jej też w wiadomości:

- czy plik był w folderze, czy tylko w czacie,
- czy wtyczka hg-probe-panel została dodana, a jeśli tak, czy obok czatu pojawiła się ramka z napisem "hg-probe: panel działa",
- zrzut ekranu, jeśli któryś krok wyglądał inaczej niż tutaj.

## 6. Po wszystkim

Dopóki wtyczki są włączone, zostawiają mały plik w każdym folderze, w którym zaczniesz rozmowę. Gdy raport zostanie wysłany, możesz wyłączyć lub usunąć hg-probe i hg-probe-panel tam, gdzie były dodane. Folder `hg-probe` możesz skasować.

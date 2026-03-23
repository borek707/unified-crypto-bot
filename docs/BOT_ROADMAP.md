# Bot Roadmap

## Cel

Celem na najblizsze iteracje nie jest budowa pelnego bota RL, tylko uporzadkowany rozwoj obecnego systemu:

1. poprawa logiki rynku,
2. stabilizacja wynikow backtestu,
3. lepsze wykorzystanie trendu,
4. dopiero potem decyzja, czy warto inwestowac czas w ML lub RL.

## Stan obecny

Bot ma juz:

1. 5-stanowy classifier rynku,
2. routing strategii zalezny od regime,
3. pierwsza warstwe trend-following,
4. dzialajacy backtest w scripts/backtest_unified.py,
5. logike live w skills/passivbot-micro/scripts/unified_bot.py.

Wynik praktyczny jest lepszy niz na poczatku, ale nadal sa dwa glowne ograniczenia:

1. bot nadal za slabo monetyzuje dlugie hossy,
2. backtest nie jest jeszcze idealnie domkniety jako narzedzie decyzyjne.

## Priorytety

Najpierw poprawiamy to, co daje najlepszy stosunek pracy do efektu:

1. zgodnosc backtestu z live,
2. lepszy classifier rynku,
3. prawdziwy trend-following,
4. lepsza kontrola ryzyka,
5. dopiero potem sandbox badawczy i ewentualne ML/RL.

## Faza 1: Fundamenty Backtestu

Priorytet: najwyzszy

Szacowany czas: 2-4 dni

Zakres:

1. Doprowadzic backtest do zgodnosci 1:1 z logika live.
2. Uporzadkowac typy pozycji:
   - long_grid
   - trend_follow
   - sideways
   - short
3. Oczyscic logike Circuit Breakera w backtescie.
4. Ujednolicic raportowanie per-strategy i per-regime.

Rezultat:

1. wiarygodniejsze liczby w testach 1y, 2y, 3y,
2. brak artefaktow w breakdownie strategii,
3. backtest gotowy do podejmowania decyzji rozwojowych.

Kryterium ukonczenia:

1. wyniki sa powtarzalne,
2. CB nie produkuje nienaturalnych aktywacji,
3. raport backtestu poprawnie rozbija wynik na strategie i regime.

## Faza 2: Lepsza Logika Rynku

Priorytet: bardzo wysoki

Szacowany czas: 1-3 dni

Zakres:

1. Dodac ADX jako filtr sily trendu.
2. Dodac multi-EMA context:
   - 48h,
   - 7d,
   - 30d.
3. Dopracowac progi dla stanow:
   - strong_uptrend,
   - pullback_uptrend,
   - sideways,
   - bear_rally,
   - strong_downtrend.
4. Ograniczyc przypadki, w ktorych rynek trafia do sideways tylko dlatego, ze nie przebil jednego progu.
5. Rozszerzyc kontekst EMA poza 3 interwaly, docelowo do koszyka okien (np. 5d, 10d, 20d, 30d, 50d, 100d).
6. Traktowac ADX i multi-EMA jako elementy state space (nie tylko twarde IF/ELSE).
7. Dodac tryb walidacyjny pod przyszly ensemble:
   - okresowa walidacja (np. rolling 3 miesiace),
   - metryka wyboru: Sharpe + kontrola drawdown,
   - bez automatycznego wlaczania RL w live na tym etapie.

Rezultat:

1. classifier lepiej rozumie rynek,
2. routing strategii dostaje lepszy kontekst,
3. mniej falszywych longow i mniej przypadkowych shortow.
4. przygotowany grunt pod selekcje strategii oparta o wyniki walidacyjne zamiast sztywnych przelacznikow.

Kryterium ukonczenia:

1. bardziej realistyczny udzial sideways,
2. mocniejsze rozroznienie miedzy trendem, korekta i rajdem w bessie,
3. poprawa wynikow bez sztucznego zwiekszania liczby transakcji,
4. ADX i koszyk EMA faktycznie poprawiaja stabilnosc klasyfikacji na testach 1y i 2y.

## Faza 3: Prawdziwy Trend-Following

Priorytet: bardzo wysoki

Szacowany czas: 2-4 dni

Zakres:

1. Rozwijac trend_follow jako glowna strategie dla strong_uptrend.
2. Ograniczyc lub wylaczyc pullback long_grid jako osobna sciezke testowa.
3. Rozwinac trend_follow:
   - lepszy trailing stop,
   - opcjonalny partial take profit,
   - re-entry po kontynuacji trendu,
   - sensowny hard stop.
4. Przetestowac wariant:
   - short + sideways + trend_follow,
   - bez starego pullback long_grid.
5. Przygotowac PPO jako silnik trend-following (najpierw offline):
   - ciagla przestrzen akcji od -1 do 1 (target exposure),
   - reward oparty o zmiane equity po fee i slippage,
   - clipping i stabilny trening przez gotowy stack PPO.
6. Potraktowac re-entry/exit jako efekt polityki modelu, a nie twarde reguly, ale zawsze pod warstwa risk constraints.

Rezultat:

1. bot lepiej wykorzystuje dluzsze ruchy wzrostowe,
2. mniejsza tendencja do zbyt szybkiego oddawania trendu,
3. trend_follow staje sie realnym zrodlem wyniku,
4. powstaje porownywalny benchmark: rule-based trend_follow vs PPO trend-follow.

Kryterium ukonczenia:

1. 3-letni backtest poprawia sie wzgledem obecnego wariantu,
2. trend_follow daje dodatni i istotny wklad do PnL,
3. long_grid przestaje byc glownym zrodlem problemow,
4. PPO przechodzi walidacje offline przed jakimkolwiek uzyciem w live.

## Faza 4: Tani Upgrade Risk Management

Priorytet: wysoki

Szacowany czas: 1-2 dni

Zakres:

1. Dodac turbulence index jako kill switch.
2. Gdy turbulence przekracza prog:
   - brak nowych wejsc,
   - zamkniecie lewarowanych pozycji,
   - pauza do uspokojenia rynku.
3. Dodac prosty model slippage do backtestu.
4. Urealnic turnover cost.

Rezultat:

1. lepsza obrona kapitalu przy skrajnej zmiennosci,
2. bardziej realistyczne testy,
3. mniejsze ryzyko katastrofalnych wejsc w chaosie rynkowym.

Kryterium ukonczenia:

1. drawdown poprawia sie w trudnych okresach,
2. wyniki backtestu sa blizsze warunkom realnym,
3. kill switch dziala przewidywalnie i nie jest zbyt czuly.

## Faza 5: Wybor Wariantu Strategii

Priorytet: sredni

Szacowany czas: 2-4 dni

Zakres:

1. Zrobic prosty selection layer zamiast pelnego ensemble RL.
2. Co tydzien lub miesiac liczyc rolling score dla 2-3 wariantow:
   - defensywny,
   - trend-follow,
   - short-plus-sideways.
3. Wybierac wariant po najlepszym Sharpe lub score typu return minus kara za drawdown.

Rezultat:

1. system zaczyna dopasowywac sie do rynku,
2. bez wdrazania PPO, A2C i DDPG,
3. niskie ryzyko operacyjne.

Kryterium ukonczenia:

1. rolling wybor wariantu daje lepsze wyniki niz jedna statyczna konfiguracja,
2. logika jest nadal prosta do utrzymania,
3. system umie przechodzic miedzy trybami bez chaosu.

## Faza 6: Maly Sandbox Badawczy

Priorytet: sredni

Szacowany czas: 4-7 dni

Zakres:

1. Wydzielic environment i reward z backtestu.
2. Dodac transaction-cost-aware reward.
3. Zbudowac feature builder:
   - RSI,
   - ADX,
   - ATR,
   - BB position,
   - 24h return,
   - 72h return,
   - funding bias.
4. Przygotowac research module pod klasyfikator rynku, nie od razu pod live DQN.

Rezultat:

1. osobne srodowisko do eksperymentow,
2. brak ryzyka rozwalania logiki live,
3. gotowa baza pod lekki klasyfikator ML.

Kryterium ukonczenia:

1. mozna trenowac i testowac klasyfikator offline,
2. live bot korzysta tylko z inferencji albo z regul,
3. badania nie wymagaja przepisywania glownego bota.

## Faza 6A: Tor PPO Dla Tego Repo

Priorytet: niski przed domknieciem faz 2-4, sredni po ich ukonczeniu

Szacowany czas: 5-10 dni na wersje badawcza offline

PPO ma sens w tym projekcie tylko jako modul badawczy offline, nie jako natychmiastowy zamiennik obecnej logiki live.

Powod:

1. PPO rzeczywiscie dobrze lapie trend, ale tylko gdy dostaje sensowny state, reward i realistyczne koszty.
2. Na obecnym etapie wiekszym problemem jest nadal logika regime i risk management niz brak samego RL.
3. Wdrozenie PPO bez wiarygodnego sandboxa tylko ukryje problemy strategii pod warstwa modelu.

Zakres implementacyjny:

1. Zbudowac osobne srodowisko gymnasium oparte na backtescie.
2. Nie podlaczac PPO bezposrednio do live execution.
3. Najpierw trenowac i walidowac offline na danych historycznych.
4. Dopuscic PPO do decyzji live dopiero po przejsciu przez bramke metryk.

### State Space

Minimalny stan dla PPO powinien zawierac:

1. stan portfela:
   - wolne saldo,
   - equity,
   - ekspozycja netto,
   - liczba i typ otwartych pozycji,
   - unrealized PnL,
2. stan rynku:
   - close,
   - return 24h,
   - return 72h,
   - return 7d,
   - odchylenie od EMA,
   - realized volatility,
3. wskazniki:
   - RSI,
   - ADX,
   - ATR,
   - MACD,
   - Bollinger position,
4. kontekst strategii:
   - aktualny regime z classifiera,
   - turbulence flag,
   - spread/slippage proxy,
   - funding bias, jesli bedzie dostepny.

Wniosek praktyczny:

1. PPO nie powinno dostawac surowej ceny i tyle.
2. Obecny classifier rule-based nadal moze byc elementem stanu, a nie koniecznie konkurencja dla PPO.

### Action Space

Najbardziej sensowny wariant dla tego repo:

1. ciagla akcja w zakresie od -1 do 1,
2. mapowanie:
   - od -1 do 0: short exposure,
   - 0: hold,
   - od 0 do 1: long exposure,
3. dodatkowe ograniczenia wykonania:
   - max leverage,
   - max total exposure,
   - kill switch,
   - limit zmian pozycji na krok.

Rekomendacja:

1. Nie dawac PPO pelnej swobody w warstwie execution.
2. Akcja PPO powinna byc target exposure, a nie surowe zlecenie rynkowe.
3. Warstwa wykonawcza dalej musi pilnowac ryzyka.

### Reward Function

Nagroda powinna byc liczona jako zmiana wartosci portfela po kosztach.

Minimalna wersja:

1. reward = equity_t+1 - equity_t - fees - slippage_cost

Wersja praktyczna dla tego bota:

1. dodatnia nagroda za wzrost equity,
2. kara za turnover,
3. kara za drawdown,
4. kara za wejscie podczas aktywnego turbulence,
5. opcjonalnie niewielka kara za bezsensowne flipowanie long-short-long.

Wniosek praktyczny:

1. Sam profit bez kosztow nie wystarczy.
2. Sam Sharpe nie powinien byc rewardem krok po kroku.
3. Sharpe powinien byc metryka walidacyjna modelu, nie glowna nagroda lokalna.

### PPO Itself

To, co faktycznie odroznia PPO od prostego policy gradient, to clipping aktualizacji polityki.

W praktyce dla tego repo oznacza to:

1. uzyc gotowej implementacji stable-baselines3,
2. zaczac od konserwatywnego clip range,
3. pilnowac entropy bonus, zeby model nie zapadl sie zbyt szybko,
4. trenowac na walk-forward splitach, a nie na jednym ciagu danych.

Rekomendacja:

1. Nie implementowac PPO od zera.
2. Skorzystac z gotowego stacku:
   - gymnasium,
   - stable-baselines3,
   - torch.

### PPO Jako Element Ensemble

Najbardziej sensowne miejsce PPO w tym projekcie to nie tryb always-on, tylko selekcja wariantu strategii.

Schemat:

1. trenowac PPO offline,
2. rownolegle utrzymac wariant rule-based i ewentualnie pozniej A2C lub DDPG,
3. co okres walidacyjny porownywac modele po:
   - Sharpe,
   - Max Drawdown,
   - Return,
   - stabilnosci wynikow,
4. dopuszczac PPO do handlu tylko wtedy, gdy wygrywa walidacje.

Wniosek praktyczny:

1. PPO nie powinno byc jedynym agentem na kazdy rynek.
2. W hossie moze byc bardzo mocne.
3. W choppy albo panicznych warunkach dalej potrzebny jest filtr ryzyka i kill switch.

### Turbulence Index

Niezaleznie od PPO potrzebny jest zewnetrzny bezpiecznik.

Minimum:

1. turbulence index jako osobny sygnal risk-off,
2. przy wysokiej turbulencji:
   - brak nowych wejsc,
   - redukcja ekspozycji,
   - zamkniecie lewarowanych pozycji,
3. turbulence nie moze zalezec od decyzji modelu.

To powinno byc wspolne dla:

1. rule-based,
2. PPO,
3. przyszlego ensemble.

### Bramka Dopuszczenia PPO

PPO ma sens dopiero wtedy, gdy spelnia jednoczesnie kilka warunkow:

1. wygrywa z rule-based na walk-forward testach,
2. nie pogarsza max drawdown ponad ustalony prog,
3. utrzymuje przewage po fee i slippage,
4. dziala stabilnie na 1y, 2y i 3y,
5. nie wymaga ciaglego retuningu co kilka dni.

Jesli te warunki nie sa spelnione, PPO zostaje tylko narzedziem badawczym.

## Faza 6B: Tor A2C Dla Sideways i Bessy

Priorytet: niski przed domknieciem faz 2-4, sredni po ukonczeniu 6A

Szacowany czas: 6-12 dni na wersje badawcza offline

A2C ma sens w tym repo jako defensywny agent dla choppy rynku, konsolidacji i slabszych warunkow trendowych.

Powod:

1. A2C zwykle daje bardziej stabilne decyzje i mniejsza zmiennosc niz agresywne trend-follow.
2. W warunkach falszywych wybic moze ograniczac overtrading.
3. W ensemble moze pelnic role "obroncy kapitalu" obok PPO.

Zakres implementacyjny:

1. Trening tylko offline, bez podlaczania do live execution.
2. Ta sama warstwa danych i risk constraints co dla PPO.
3. Porownanie A2C vs PPO vs rule-based na identycznych splitach walk-forward.
4. Routing tylko przez walidacje metryk, nie przez reczne progi IF/ELSE.

### Architektura i uczenie

W praktyce dla tego projektu:

1. Uzyc gotowej implementacji A2C (stable-baselines3) zamiast pisania od zera.
2. Trzymac rownolegle wiele rolloutow (vectorized env), aby zwiekszyc roznorodnosc probek i stabilnosc gradientu.
3. Utrzymac wspolny pipeline state/action/reward z torem PPO.

### Advantage Function

Rdzen A2C to funkcja przewagi:

1. A(s_t, a_t) = r_t + gamma * V(s_t+1) - V(s_t)

Wniosek praktyczny:

1. Jezeli ruch ceny jest glownie szumem, przewaga bedzie mala i agent nie powinien nadmiernie handlowac.
2. To wspiera cel fazy 2: mniej falszywych longow i przypadkowych shortow.

### Action Space i objective

1. Ciagla akcja od -1 do 1 jako target exposure.
2. Polityka probabilistyczna nad akcja ciagla.
3. Ograniczenia wykonawcze jak w PPO: max leverage, max exposure, turbulence kill switch.

### Rola w ensemble

A2C nie powinien byc uruchamiany "na sztywno" po wykryciu sideways.

Docelowy routing:

1. Modele PPO, A2C i wariant rule-based sa walidowane w rolling oknie (np. 3 miesiace).
2. Wybor aktywnego agenta odbywa sie po metrykach:
   - Sharpe,
   - Max Drawdown,
   - Return po kosztach,
   - stabilnosc wynikow.
3. Agent o najlepszym profilu ryzyko-zwrot dostaje kolejny okres handlu.

### Bramka dopuszczenia A2C

A2C przechodzi dalej tylko gdy:

1. poprawia drawdown i zmiennosc wzgledem PPO/rule-based,
2. nie traci przewagi po fee i slippage,
3. utrzymuje stabilnosc na 1y, 2y i 3y,
4. nie wymaga ciaglego retuningu.

Jesli warunki nie sa spelnione, A2C zostaje modulem badawczym.

## Faza 7: ML lub RL Tylko Jezeli Jest Przewaga

Priorytet: niski na teraz

Szacowany czas: 1-3 tygodnie

Zakres:

1. Sprawdzic, czy klasyfikator offline daje realna przewage nad rule-based.
2. Jesli tak, wdrozyc lekki model klasyfikacji reżimu.
3. Jesli nie, nie isc dalej w RL.
4. PPO traktowac jako pierwszy kandydat RL do testow offline.
5. A2C traktowac jako defensywnego kandydata po torze PPO.
6. DDPG rozpatrywac dopiero po PPO i A2C.

Rezultat:

1. brak przepalania czasu na RL bez przewagi,
2. rozwijane sa tylko te elementy, ktore realnie poprawiaja wynik,
3. mozliwosc wejscia w ML na bazie gotowych danych i metryk,
4. jasna decyzja, czy PPO ma sens jako agent albo jako element ensemble.

## Co Wdrazac Od Razu

Najbardziej pragmatyczna kolejnosc:

1. Domknac backtest i Circuit Breaker.
2. Dodac ADX i multi-EMA do classifiera.
3. Zrobic wariant short + sideways + trend_follow bez pullback long_grid.
4. Dodac turbulence kill switch.
5. Dopiero potem bawic sie selection layer i sandboxem.

## Czego Nie Robic Teraz

Na obecnym etapie nie warto od razu wdrazac:

1. pelnego DQN,
2. uczenia online,
3. ensemble PPO/A2C/DDPG bez wczesniejszego offline gate,
4. sentiment/news,
5. rozbudowanego Actor-Critic stack.

To sa sensowne kierunki badawcze, ale przedwczesne wobec tego, co nadal mozna poprawic w obecnym rule-based core.

## Minimalny Plan Operacyjny

Najbardziej praktyczne trzy kroki na teraz:

1. Uspojnic backtest z live.
2. Zastapic pullback long_grid wariantem trend_follow only in strong_uptrend.
3. Dodac ADX oraz turbulence.

To jest najlepszy stosunek pracy do efektu.

## Co Zostalo Zrobione: Logika Krok Po Kroku

Ponizej jest realny przebieg prac, tak jak byly wykonywane iteracyjnie.

### Krok 1: Audyt kodu i architektury

1. Przeczytano aktualna logike live bota.
2. Sprawdzono stan dokumentacji i historycznych wynikow.
3. Zweryfikowano brak gotowego, wiarygodnego backtestu 1:1 dla aktualnej logiki.

Wniosek:

1. Najpierw trzeba bylo zbudowac i domknac backtest, dopiero potem stroic strategie.

### Krok 2: Budowa nowego backtestu unified

1. Dodano [scripts/backtest_unified.py](scripts/backtest_unified.py).
2. Zaimplementowano podstawowe strategie i metryki.
3. Odpalono pierwsze testy 1y i zebrano baseline.

Wniosek:

1. Wyniki ujawnily slabosc long-side i problemy klasyfikacji regime.

### Krok 3: Pierwsza iteracja poprawek strategii

1. Dodano porownania wariantow (v1/v2/v3).
2. Przetestowano m.in. bardziej defensywne ustawienia i ograniczenia long-grid.
3. Po kazdej zmianie odpalano test porownawczy 1y.

Wniosek:

1. Sam tuning parametrow nie wystarczal, potrzebna byla zmiana logiki rynku.

### Krok 4: Przebudowa klasyfikatora rynku

1. Przejscie z prostego podejscia na 5 stanow regime:
   - strong_uptrend,
   - pullback_uptrend,
   - sideways,
   - bear_rally,
   - strong_downtrend.
2. Dodanie multi-horizon kontekstu (48h/7d/14d/30d + EMA baseline).
3. Synchronizacja tej logiki miedzy live i backtestem.
4. Testy: 1y, potem 2y, potem 3y.

Wniosek:

1. Byla wyrazna poprawa klasyfikacji, ale dlugi horyzont nadal przegrywal z HODL.

### Krok 5: Warstwa trend-following

1. Dodano osobny typ pozycji trend_follow.
2. Dodano hard stop i trailing stop.
3. Wpięto zarzadzanie trend_follow do routingu live i backtestu.
4. Po wdrozeniu odpalono pelne porownania 1y/2y/3y.

Wniosek:

1. Technicznie dziala poprawnie, ale wynik dlugoterminowy nadal wymaga poprawy.

### Krok 6: Domykanie fazy 1 (backtest parity)

1. Uporzadkowano typy pozycji i wyjscia.
2. Poprawiono logike Circuit Breakera i reset dzienny.
3. Dodano raportowanie per-strategy i per-regime.
4. Dodano limity ekspozycji i poprawiono rozliczanie fee.
5. Testy regresyjne po kazdej wiekszej poprawce.

Wniosek:

1. Backtest stal sie bardziej wiarygodny jako narzedzie decyzyjne.

### Krok 7: Rozszerzenie roadmapy o RL tracks

1. Dodano tor PPO (offline-first, gate przed live).
2. Dodano tor A2C jako defensywny agent dla choppy/sideways.
3. Ustalono routing przez walidacje metryk, a nie przez twarde IF/ELSE dla modeli RL.

Wniosek:

1. RL jest traktowany jako kolejny etap po stabilizacji rule-based core i po przejsciu bramek metryk.

### Jak wyglada cykl pracy (standard)

Kazda iteracja byla realizowana wedlug tego samego schematu:

1. implementacja jednej konkretnej zmiany,
2. szybka walidacja techniczna,
3. backtest porownawczy,
4. analiza metryk i breakdownu,
5. decyzja: zostawic, poprawic albo wycofac,
6. dopiero potem kolejny krok.

To podejscie jest rekomendowane rowniez dalej, szczegolnie przy fazie 2 i torach PPO/A2C.
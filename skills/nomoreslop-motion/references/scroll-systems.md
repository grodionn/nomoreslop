# Скролл и движение: выбор механики, реализация и приёмка

Разделы: 1. Три разных смысла smooth · 2. Основные модели управления · 3. Каталог приёмов: шире parallax · 4. Выбор технической основы · 5. Эталонные примеры и способы получения · 6. Контракт сцены до полировки · 7. Доступность и контроль пользователя · 8. Стресс-проверка и наблюдаемые дефекты · 9. Что реально подтверждено при сборе.

Справочник для выбранной scroll-задачи: появление, чтение, навигация, сцена или последовательность. Проверено по первичной документации 29 октября 2026 через web/HTTP. Имена API и возможности сопоставляй с установленной версией. «Эталон» ниже означает доступный технический образец объяснённой механики, а не универсальный стиль и не визуально сертифицированный компонент.

## 1. Три разных смысла smooth

1. **Нативная прокрутка.** Браузер управляет wheel, trackpad, touch, scrollbar и клавиатурой. Контент перемещается обычным способом; дополнительные библиотеки не обязательны.
2. **Плавное перемещение к цели.** Якорь или программная команда переводит scroll position к элементу. `scroll-behavior:smooth` относится к такой навигации/API; не сглаживает весь wheel-ввод. Кривую и длительность выбирает user agent, а не CSS-параметры автора. [MDN scroll-behavior](https://developer.mozilla.org/en-US/docs/Web/CSS/scroll-behavior).
3. **Плавный вид эффекта при прокрутке.** Reveal, parallax или progress связывается с viewport/scroll. «Плавный» может означать качественный rendering без пропусков кадров, мягкую кривую, пружину либо задержанное догоняющее движение. Эти свойства различны. Сглаживать сам scroll для плавного reveal обычно не требуется.

Не добавляй Lenis, ScrollSmoother и перехват wheel каждому сайту от слова «smooth». Сначала выбери конкретную проблему: якорный переход, дрожание привязанного визуала, плохая производительность, нужное инерционное ощущение или сценарий демонстрации. Локальная правка dropdown не запускает исследование прокрутки страницы.

## 2. Основные модели управления

| Модель | Что управляет прогрессом | Подходящая задача | Что определить заранее |
| --- | --- | --- | --- |
| Scroll-triggered | Пересечение порога запускает обычное time-based движение | Reveal, начало/пауза иллюстрации, вступление блока | Порог, повтор/однократность, выход/возврат, исходное состояние |
| Scroll-linked / scrubbed | Позиция в диапазоне прямо определяет progress | Reading progress, parallax, предметный переход | Начало/конец, clamp, соответствие обоим направлениям |
| View-linked | Положение объекта внутри scroller задаёт progress | Раскрытие изображения, локальный акцент | Какая часть пути используется: entry/cover/exit, viewport/container |
| Direction-aware | Направление плюс устойчивый порог меняют состояние | Скрываться вниз / возвращаться вверх у header | Hysteresis, начало страницы, focused/open states |
| Velocity-reactive | Скорость/направление влияют на эффект | Умеренная реакция графики или kinetic type | Ограничение амплитуды, отпускание, возвращение к спокойному состоянию |
| Programmatic navigation | Нажатие ведёт к выбранной позиции | Оглавление, skip link, next section | Scroll offset, URL/history, focus, отмена пользователем |
| Snap / paging | Скролл заканчивается у допустимых позиций | Галерея, короткие карточки/слайды | Proximity или mandatory, overflow длинного элемента, touch/keyboard |
| Sticky / pin | Область остаётся на месте на части пути | Сравнение, визуальная поддержка текста, рассказ | Сколько и почему держим, место в document flow, доступ к следующему |
| Smooth input layer | Библиотека сглаживает связь input → native scroll position | Уже выбранная хореография/синхронизация | Версия, единственный clock, nested scroll, anchors, reduce motion |

Фундаментальное различие triggered/linked подтверждает [Motion scroll guide](https://motion.dev/docs/react-scroll-animations). Не маскируй time-based reveal под scrub только потому, что он вызван прокруткой. Spring на progress вводит отставание: точный измеритель прочитанного и художественно догоняющая полоска — разные решения.

## 3. Каталог приёмов: шире parallax

Это карта кандидатов, не список эффектов, обязательных одной странице. В каждой строке нужно основание от содержания. Для ещё не выбранной механики вопрос пользователю нужен только при существенной развилке; не спрашивай про parallax просто потому, что он есть в каталоге.

| Приём | Варианты и задача | Существенная граница / проверка |
| --- | --- | --- |
| **Reveal блока** | Fade, малый translate, scale, clip/mask, wipe, blur-to-clear, поворот, раскрытие слоя | Главная информация не должна ждать долгую цепь; без JS/observer остаётся доступной |
| **Stagger группы** | По порядку чтения, колонкам, глубине, пространственной волне | Не делать список из 40 элементов последовательной задержкой. Группировка соответствует смыслу |
| **Повторяемый reveal** | Вход/выход, once, play/reverse, reset после полного выхода | Возврат вверх и быстрая смена направления не вызывают flash и телепортацию |
| **Изображение через маску** | Inset/curtain/circle, смена crop, scale внутри неподвижной рамки | Не менять саму область измерения без контроля feedback; изображение не исчезает в fallback |
| **Parallax глубины** | Фон, объект, ближний слой, противоположные скорости | Основной текст может оставаться неподвижным; границы картинки не открываются; reduce motion |
| **Sticky supporting visual** | Изображение остаётся, текст идёт рядом; смена визуала по главам | Sticky сам по себе не анимация. Не нужно держать пользователя в сцене ради эффекта |
| **Pinned storytelling** | Общая сцена показывает несколько состояний предмета | Состояния раскрывают новый смысл; scroll-distance пропорционален материалу; есть нормальный выход |
| **Stacked cards/panels** | Карточки перекрывают/сжимают/перелистывают предыдущие | Скрытые ссылки не должны перехватывать фокус и клик; на телефоне допустим обычный список |
| **Horizontal native rail** | Обычный overflow-x, scroll snap, buttons, progress markers | Не требует wheel remapping. Сохраняй keyboard/touch и видимый доступ к соседним элементам |
| **Vertical-to-horizontal scene** | Вертикальная позиция двигает широкий трек по X | Это transformed scene, а не нативный горизонтальный scroller. Рассчитай реальный overflow и fallback |
| **Scroll snap секций** | Proximity, mandatory, отдельные snap-stop | Длинная секция должна полностью читаться; mandatory не превращает чтение в борьбу с возвратом |
| **Reading progress** | Линия, сегменты глав, круг, локальный прогресс статьи | Прогресс считается по относящемуся scroller/материалу, а не всему footer и пустым pin-spacers |
| **Scrollspy / chapter nav** | Активная глава, underline, маркер sidebar | Активное состояние обновляется устойчиво у границы; href и focus остаются функциональными |
| **Auto-hide header/nav** | Уход вниз, возврат вверх, компактный/развёрнутый header | Не скрывать управление с фокусом/открытым меню; исключить дрожание у нулевой скорости |
| **Cover-to-header** | Большая обложка становится компактным заголовком | Сохранить место в потоке и конечный кегль; геометрия движения не ломает длину документа |
| **Текст по scroll** | Highlight строк/слов, маска, смена weight/оси, scrubbed reveal | Порядок чтения и текстовая альтернатива сохраняются; нельзя требовать ловить нужный кадр |
| **SVG draw/path progress** | Линия маршрута, соединения, контур, marker вдоль пути | Движение связано со смыслом схемы; длины пути/viewport корректны; статический конечный вид |
| **Смена изображения/scene state** | Crossfade, frame sequence, sprite, video scrub | Отдельно измерить decode/память/загрузку; не обещать мгновенный scrub удалённого видео |
| **Scroll-linked 3D** | Camera orbit, exploded view, материалы, поворот/детали | Motion задаёт сценарий/диапазон, 3d — сцену; без готовых данных камера не создаёт детализацию |
| **Depth/zoom transition** | Приближение объекта, проход через слой, перспектива | Большие optical-flow движения могут быть тяжёлыми для восприятия; спокойный режим обязателен по задаче |
| **Velocity effects** | Skew, растяжение, смена темпа ticker, смещение декора | Не привязывать размер текста/клик-цели к бесконтрольной скорости; возврат к нулю |
| **Scroll-linked color** | Изменение поверхности/темы участка, gradient shift | Контраст проверяется по пути и слоям; тема продукта и декоративный цвет участка различаются |
| **Edge hints / overflow affordance** | Тень края, маска, исчезающая подсказка продолжения | Декор не подменяет видимый следующий фрагмент, scrollbar и работающее управление |
| **Back-to-top / next chapter** | Мгновенный или плавный переход к цели | Не вставлять кнопку в каждый экран автоматически; проверить offset, остановку и URL/focus |
| **Infinite/paginated list** | Подгрузка с sentinel, восстановление позиции | Это UX и данные, а не просто анимация: доступный следующий шаг, footer, history, loading/error |

Сочетай одну ведущую механику с нужными поддерживающими, а не все эффекты одновременно. Если содержимого мало, более сложная сцена не создаёт новую историю. Термины smooth, sharp, elastic описывают характер движения, а pin, snap, reveal — механизм/роль; это не взаимозаменяемые категории.

## 4. Выбор технической основы

### Native CSS и IntersectionObserver

Используй обычную разметку и прокрутку как работающую основу. Для якоря с fixed-header учитывай `scroll-padding` на scroller или `scroll-margin` цели. Не расставляй ручные `top:-100px` вокруг всех heading. [MDN scroll-padding-top](https://developer.mozilla.org/en-US/docs/Web/CSS/scroll-padding-top).

CSS sticky подходит, когда нужна фиксация в рамках контейнера без timeline. Проверь ближайший scrolling ancestor, overflow предков, inset и доступную высоту. У sticky есть собственный stacking context; это может влиять на overlay. [MDN position](https://developer.mozilla.org/en-US/docs/Web/CSS/position).

IntersectionObserver даёт асинхронное пересечение с root и порогами, пригодное для вступления/паузы, sentinel и активной главы. Это не точный покадровый датчик scroll position. Выбирай root/rootMargin/threshold от компонента, удаляй observer при unmount; слишком высокий порог может никогда не достигаться у большой секции. [MDN Intersection Observer](https://developer.mozilla.org/en-US/docs/Web/API/Intersection_Observer_API).

Для галереи оцени CSS Scroll Snap до собственного wheel-engine: `scroll-snap-type`, `scroll-snap-align`, padding/margin и scrollable overflow образуют систему. Proximity обычно менее принудителен, но выбор зависит от сценария. [MDN Scroll Snap](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_scroll_snap).

### CSS scroll/view timelines и WAAPI

`scroll()` связывает animation progress с scroller, `view()` — с положением наблюдаемого элемента. Именованные timelines нужны для разделённых элементов/областей. Объявляй timeline после `animation` shorthand: тот может сбросить timeline. На проверке MDN помечал `animation-timeline` как Limited availability: проверяй актуальные браузеры проекта и делай статический либо JS fallback. [MDN animation-timeline](https://developer.mozilla.org/en-US/docs/Web/CSS/animation-timeline).

`animation-range` задаёт используемую часть timeline: entry, cover, contain, exit или численные границы по поддерживаемому синтаксису. Не копируй `entry 25% cover 50%` как порог каждого reveal — измеряй собственное изображение и время чтения. [MDN animation-range](https://developer.mozilla.org/en-US/docs/Web/CSS/animation-range).

Для технического изучения доступны CSS/WAAPI-примеры [Chrome Developers](https://developer.chrome.com/docs/css-ui/scroll-driven-animations). Декларативный scroll timeline может убрать main-thread synchronisation для подходящих свойств; это не делает любые blur/height/огромные слои бесплатными. Проверяй свойства, paint и реальное поведение.

### Motion

`whileInView`/`useInView` — ветка triggered. Явно выбери `once`, root, margin и amount; состояние «полностью виден» не подходит каждому длинному блоку. Для невидимого после первой загрузки контента предусмотрен доступный исходный/fallback-вид. [Motion component viewport](https://motion.dev/docs/react-motion-component), [useInView](https://motion.dev/docs/react-use-in-view).

Для linked используй `useScroll` с container, target, axis и offset. Progress можно передать в значение движения без React state на каждом кадре; `useTransform` задаёт карту. Размер content может измениться после загрузки: актуальная документация имеет `trackContentSize`, по умолчанию false. Target измеряется в layout-позиции; transform его/предков не переносит измеренную цель. Проверь версию проекта. [Motion useScroll](https://motion.dev/docs/react-use-scroll).

Не сглаживай точное состояние до неопределённой задержки. `useSpring(scrollYProgress)` может дать приятную инерцию для декоративной линии, но на изображении, которое обязано соответствовать точной позиции, потребует объяснённого компромисса.

### GSAP ScrollTrigger

Для сложной сцены задавай один владелец timeline: trigger/scroller, start/end, pin, scrub или toggleActions, reverse и завершение. `scrub:true` напрямую связывает playhead с progress, число добавляет догоняющее время. При scrub длительности внутренних tween определяют пропорции scroll-distance. Animate дочернее содержимое, не сам измеряемый pinned элемент. У `containerAnimation` для transformed-horizontal нужны linear ease и специальные ограничения: pin/snap на вложенных containerAnimation-триггерах не поддерживаются. [ScrollTrigger](https://gsap.com/docs/v3/Plugins/ScrollTrigger/).

Не назначай scrub одновременно родительскому timeline и вложенным tween: два владельца playhead конфликтуют. Сопоставь повторные изменения одного свойства с cached start values; `fromTo`, единая последовательность или отдельные wrappers могут быть правильнее конкурирующих `to`. Не используй refresh как постоянную покадровую заплатку. [GSAP tips and mistakes](https://gsap.com/resources/st-mistakes/).

После изменения layout — загрузки изображения/шрифта, expand, смены колонок — обнови измерения. `refresh()` пересчитывает start/end по текущей геометрии, `update()` только обновляет позицию/связанные состояния. Function-based размеры и `invalidateOnRefresh` применяй к тому, что реально зависит от геометрии. [ScrollTrigger.refresh](https://gsap.com/docs/v3/Plugins/ScrollTrigger/static.refresh()/).

Разные layouts и reduced motion организуй через `gsap.matchMedia()`: сборка подходящей ветки, revert при смене условий, собственная cleanup для не-GSAP ресурсов. React-интеграция должна переживать remount/Strict Mode; scoped `useGSAP`/context и cleanup не позволяют копить слушатели и pin-spacers. [matchMedia](https://gsap.com/docs/v3/GSAP/gsap.matchMedia()/), [React guide](https://gsap.com/resources/React/).

### Smooth input layer: Lenis

Изучи текущий [официальный README](https://github.com/darkroomengineering/lenis) и установленную версию. Проверенная документация описывает работу поверх native scroll, anchors, nested regions и опции loop. Нативный touch нельзя считать проверенным по wheel-демо. С Lenis+GSAP используй один RAF-clock; не запускай одновременно autoRaf и второе ручное обновление. Учитывай units секунд/миллисекунд и удаление ticker callback.

В проверенной документации anchors и автоматический nested-scroll были выключены по умолчанию; `prevent` позволяет адресно исключить modal, а автоматическое распознавание nested-областей имеет стоимость. Современный README также описывает автоматическую реакцию на `prefers-reduced-motion`, но старые версии могут не иметь её. Проверь фактическое поведение и свои дополнительные эффекты: остановка smoothing не выключает parallax автоматически. Не копируй изменение глобального GSAP ticker как настройку всех проектов без оценки соседних анимаций.

Smooth scrolling не даёт разрешения ломать scrollbar, поиск текста, hash links, history/back, native touch и фокус. Если нет причины внедрять input-layer, сохрани native scroll.

## 5. Эталонные примеры и способы получения

| Образец | Чему учиться | Как получить и что изменить |
| --- | --- | --- |
| [CSS Reading Progress](https://scroll-driven-animations.style/demos/progress-bar/css/) | Ясное соответствие document-progress и полосы, `scroll()` | HTML содержит объяснение и код; прочитать через HTTP, получить только нужный snippet/связанный CSS. Заменить scope на свой материал, не копировать demo-контент |
| [Image Reveal](https://scroll-driven-animations.style/demos/image-reveal/css/) | Opacity + clip как одно раскрытие, view-range вместо произвольного таймера | Доступны именованный/анонимный CSS и WAAPI-варианты. Изучить исходник страницы, выбрать stack/поддержку, настроить маску/порог и спокойный вид |
| [Cover to Fixed Header](https://scroll-driven-animations.style/demos/cover-to-fixed-header/css/) | Вход большого cover в малый header и сохранение места в потоке | В HTML объяснён fixed и компенсация document-space. Не копировать высоты/vh слепо; заголовок, zoom, fixed overlap и paint проверяются отдельно |
| [Horizontal Carousel Indicator](https://scroll-driven-animations.style/demos/horizontal-carousel/css/) | Локальный scroller и шаги индикатора; независимость нескольких rails | Изучить named timeline/WAAPI альтернативы. Сохранять native overflow и реальную связь индикатора с rail, не внедрять vertical remap |
| [Motion React scroll guide](https://motion.dev/docs/react-scroll-animations) | Разделение triggered/linked, progress/parallax examples | Официальные code blocks и examples через HTTP/docs/MCP при наличии. Проверить текущий импорт и бесплатность выбранного примера |
| [GSAP ScrollTrigger examples](https://gsap.com/docs/v3/Plugins/ScrollTrigger/) | Pin/scrub/snap, один timeline, callbacks и return direction | Code blocks страницы и авторские связанные demo. Получить HTML/CSS/JS/зависимости конкретного примера; каталог/showcase не равен лицензии на чужой сайт |
| [Lenis integration](https://github.com/darkroomengineering/lenis) | Single-clock sync и адресные исключения scrollable modal | README и выбранные авторские файлы/версия через GitHub HTTP. Не добавлять библиотеку по одной эстетической метке; установка/изменение проекта остаётся в задаче реализации |

Эти образцы демонстрируют механику. Они не отменяют поиска более подходящего компонента по стилю, UX-компоновке, стеку и содержанию текущего продукта. Сохранённый известный пример не становится новой выдачей, а красивые screenshots не доказывают runtime/обратный ход. Исходные фото/тексты/логотипы демо не переносятся автоматически.

## 6. Контракт сцены до полировки

Для выбранной нетривиальной сцены определяй в общей записи проекта, а не в новом параллельном журнале:

- **Задача и наблюдаемое свойство:** что движение раскрывает и каким должен быть конечный результат.
- **Владелец:** native scroller, timeline, direction state или input-layer; кто управляет каждой анимируемой величиной.
- **Геометрия:** container/target, измеряемый wrapper, диапазон, ширина overflow, spacer и место следующей секции.
- **Время/дистанция:** событие или progress; повтор/once/reverse, допустимое отставание и остановка.
- **Переходы:** прямой/обратный ход, быстрый skip через диапазон, вход в середине страницы, прерывание, resize, восстановление history.
- **Режимы:** narrow/touch/keyboard, reduced motion, отсутствие/ошибка JS или media, локали/увеличение текста.
- **Ресурсы:** версия/источник компонента, изображения/видео/сцена, file dependencies, cleanup.

Малой локальной анимации достаточно затронутого контракта; не создавай восемь документов ради появления одной подписи.

## 7. Доступность и контроль пользователя

`prefers-reduced-motion` — сигнал предпочтения, не сертификат доступности. Для выбранного избыточного пространственного движения предусмотрен спокойный вариант: убрать parallax, убрать/сократить pin, показать важное конечное состояние и сохранить действия. Держать человека на пустом scroll-distance без визуала после отключения движения — дефект. Проверяй смену предпочтения во время работы. [MDN prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion).

WCAG **2.3.3 — AAA**, не AA: несущественная motion animation от взаимодействия должна отключаться. Само естественное движение при прокрутке отличается от дополнительных parallax/масштабирований. Это основание ответственно проектировать спокойный режим, а не запрет выразительности. [W3C 2.3.3](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html).

WCAG **2.2.2 — A** имеет другую область: автоматически начавшиеся движение/мигание/scroll, продолжающиеся более пяти секунд рядом с другим содержимым, требуют pause/stop/hide, если не существенны; auto-updating имеет отдельную часть критерия. Нельзя считать отсутствие parallax достаточной проверкой looping ticker и постоянно движущегося фона. [W3C 2.2.2](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html).

Не переключай focus на каждом scroll reveal. Нативный tab order, видимая цель и чтение остаются согласованы; маска/opacity не должны оставлять невидимые кликабельные объекты поверх доступного слоя. Фокус в pinned/overlaid зоне, открытое меню и клавиатурная прокрутка проверяются в результате, а не по одному CSS-правилу.

## 8. Стресс-проверка и наблюдаемые дефекты

| Ситуация | Что воспроизвести и принять |
| --- | --- |
| Обычный прямой ход | Каждая важная часть видна достаточно, следующий блок достижим, нет бесцельной задержки |
| Обратный ход | Стрелка/индикатор/сцена возвращаются корректно; once-reveal не обязан скрываться обратно, если это принятое поведение |
| Быстрая смена направления | Нет competing tweens, restart с нуля и «замороженного» progress; hover/click не ждут окончания scroll-effect |
| Fast fling / Home / End | При пропуске всего диапазона состояние согласовано с текущей позицией, callbacks не единственный источник истины |
| Загрузка посередине / anchor | Правильное состояние без предварительного проигрывания всех вступлений; цель не закрыта header |
| Back/forward | Позиция восстанавливается по принятой router/history-логике; случайный scrollTo(0) не стирает путь человека. [History.scrollRestoration](https://developer.mozilla.org/en-US/docs/Web/API/History/scrollRestoration) |
| Image/font/content change | Геометрия обновляется после реального изменения; нет stale start/end и скачущего spacer |
| Resize/rotation/zoom | Границы сцены и overflow пересчитаны, текст не заблокирован; не только desktop screenshot |
| Nested modal/list | Колесо/палец двигает нужную область, закрытие восстанавливает scroll; `overscroll-behavior` решает chaining адресно. [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/overscroll-behavior) |
| Touch/keyboard | Scroll и функции доступны без hover-only жеста; horizontal rail не блокирует основной vertical scroll |
| Reduced motion | Важное содержание и действия доступны; статический вариант не сохраняет бессмысленную дистанцию pin |
| Remount/navigation | Нет дублированных RAF/listeners/observers, pin-spacers и незавершённых async callbacks |
| Тяжёлые media/filters | Измерить frame pacing, long tasks, память/decode и реальную длительность реакции в названной среде; «transform» не гарантирует плавность сцены |

Проверяй собственный результат настоящим браузерным рендером и взаимодействием, а не внешним browser-сёрфингом. Укажи viewport/браузер/ввод, проверенные направления/состояния и оставшийся предел. Если доступны только source/DOM, пометь `render_unverified` и `interaction_unverified`; не называй это доказанным smooth scroll на телефоне.

## 9. Что реально подтверждено при сборе

Через web прочитаны официальные MDN, Motion, GSAP, Lenis и W3C-пояснения, а также авторские CSS/WAAPI demo-страницы. Программный HTTP получил CSS Reading Progress (200, HTML содержит объяснение и `animation-timeline`) и текущий Lenis README (200). Первая предполагаемая image-reveal URL дала 404; после перехода по настоящей ссылке каталога найден правильный `/demos/image-reveal/css/`. Это подтверждает необходимость брать адреса из каталога, а не конструировать их из названия.

Ни демонстрации, ни собранные параметры не проигрывались в браузере; физический телефон, performance trace, реализация компонента и интеграция в пользовательский сайт в этом исследовании не проверялись. Сведения о результате страницы/документа не являются свидетельством её runtime-качества.

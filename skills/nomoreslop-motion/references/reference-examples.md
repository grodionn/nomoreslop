# Эталонные механики и что из них извлечь

Это эталоны **определённого свойства**, подтверждённые опубликованной документацией/кодом, а не рейтинг красивейших сайтов. Поиск стиля и сравнение кандидатов для нового проекта всё ещё нужны. Демонстрации во время этого исследования не исполнялись визуально; состояние качества и FPS не утверждается.

| Первичный пример | Что изучить | Как применить и где ограничить |
| --- | --- | --- |
| [Radix Accordion: animating content size](https://www.radix-ui.com/primitives/docs/components/accordion#animating-content-size) | Измеренные CSS variables ширины/высоты, open/closed ветки, chevron | Раскрытие под динамический текст; добавь проверку новой высоты после изменения контента, не растягивай буквы scaleY |
| [Radix Dropdown: origin/collision-aware](https://www.radix-ui.com/primitives/docs/components/dropdown-menu#origin-aware-animations) | Transform-origin вычисляется от размещения/стрелки, data-side меняется при столкновении | Меню раскрывается от реального источника, включая flip у края; не переносить огромную scale-амплитуду из демонстрации всем popup |
| [Radix Navigation Menu: advanced animation](https://www.radix-ui.com/primitives/docs/components/navigation-menu#advanced-animation) | Направление входа/выхода панели, связанный viewport меняет размер | Согласованная смена соседних панелей; не навешивать OS menu-role на обычную web-навигацию |
| [Motion layout](https://motion.dev/docs/react-layout-animations) и [GSAP Flip](https://gsap.com/docs/v3/Plugins/Flip/) | Связь позиции/размера между layout-состояниями, shared element | Карточка→деталь и сортировка сохраняют идентичность; содержимое и transform владельцы проверяются отдельно |
| [Motion AnimatePresence](https://motion.dev/docs/react-animate-presence) и [Radix animation guide](https://www.radix-ui.com/primitives/docs/guides/animation) | Exit требует согласованного mount/unmount lifecycle | Быстрые open→close→open не теряют панель; CSS-exit и JS presence не должны одновременно конкурировать за удаление |
| [Motion SVG: path drawing](https://motion.dev/docs/react-svg-animation) / [официальный demo URL](https://examples.motion.dev/react/path-drawing) | Progress stroke, path length/spacing/offset | Появление знака/линии; не путать прорисовку stroke с постепенной заливкой fill |
| [GSAP DrawSVG](https://gsap.com/docs/v3/Plugins/DrawSVGPlugin/) | Управляемый сегмент stroke, рисование от выбранного участка | SVG-аннотация/схема; сам плагин не анимирует fill, проверяй конечный контур |
| [GSAP MorphSVG](https://gsap.com/docs/v3/Plugins/MorphSVGPlugin/) | Соответствие точек/shapeIndex, линейный/вращательный morph | Брендовая форма и переход иконки; smoothing/redraw может изменить исходный силуэт, проверяй точность и стоимость |
| [Motion hover](https://motion.dev/docs/react-hover-animation) | Различение настоящего hover и emulated touch-событий | Pointer-отклик без «залипшего» hover после касания; смысл остаётся доступен без hover |
| [Motion drag](https://motion.dev/docs/react-drag) | Ограничение оси, elastic boundaries, momentum | Drag-панель или swipe; это не готовый доступный range-input и не полноценный dropzone |
| [WAI carousel example](https://www.w3.org/WAI/ARIA/apg/patterns/carousel/examples/carousel-1-prev-next/) | Next/previous, pause, focus и вращение | Поведенческая база слайдера, не эстетический шаблон; испытать реальные клавиатуру/touch/AT |
| [WAI media seek slider](https://www.w3.org/WAI/ARIA/apg/patterns/slider/examples/slider-seek/) | Значение, клавиатура и понятное время | Диапазон/progress управление; визуальная пружина не задерживает фактическое изменение значения |


## Выбор образца для проекта

Для scroll-механик используй [подборку scroll-образцов](scroll-systems.md#5-эталонные-примеры-и-способы-получения), для готовых элементов — [проверенные исходники](source-access.md#5-компонентные-источники-текущий-формат-и-комплект). В них оценивается конкретное переносимое поведение, а не предлагается универсальный внешний вид.

Сопоставь два относящихся кандидата на реальном содержании: что делает пользователь, какая связь состояний видна, что происходит при закрытии/обратном ходе и при быстром повторе, какое состояние остаётся без выразительного движения. При переносе сохрани полезное свойство и семантику, затем согласуй форму, ритм, цвет и масштаб с проектом. Если доступен только код или описание, называй именно этот уровень проверки; визуальный просмотр и измерение исполнения остаются отдельными.

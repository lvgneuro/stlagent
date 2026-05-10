from __future__ import annotations

import json
from pathlib import Path


ANDREA_CATALOG = """
=== КАТАЛОГ МЕБЕЛИ АНДРЕА ===
https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/

--- ДИВАНЫ ---
Алессандро: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/alessandro/ — модульный диван с регулируемым подголовником, электрическим реклайнером, механизм Пума, опция бельевой короб, мягкие подспинные подушки, изящная изогнутая форма подлокотника. Премиум.
Луиджи: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/luigi/ — диван с Г-образными опорами, 4 слоя ППУ, встроенная полка (опция), модульная система. Без механизма.
Монако: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/monaco/ — итальянский стиль, металлические опоры, механизм Венеция, шагающая спинка и подлокотники. Современная классика.
Кампус: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/campus/ — хромированные опоры, молния на подлокотниках, механизм Тик-Так, опция столешница из шпона.
Дэлтон: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/dalton/ — высокие металлические опоры, комплект подушек, для зонирования пространства.
Коузи (диван): https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/cozy/ — современные высокие опоры, беспроводная зарядка (опция), полка (опция), механизм SIZEZ.
Даллас: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/dallas/ — асимметричный модульный диван, выкатной механизм, регулируемые подголовники, реклайнер, бар, электромассажер (опции).
Милан: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/milan/ — прямой диван, механизм Венеция, хромированные молдинги, изогнутый силуэт, мягкие округлые формы.
Палермо: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/palermo/ — модульный в стиле контемпорари, выкатной механизм, регулируемая глубина посадки 48-62 см.
Неаполь: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/neapol/ — угловой модульный трансформер, 8 режимов наклона спинки, широкие подлокотники.
Марко: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/marco/ — механизм Пума, съёмные валики-аэропух вдоль спинки, глубокая посадка.
Дюна: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/dune/ — для релаксации, металлические опоры, шагающая спинка, обволакивающие формы.
Остерманн: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/ostermann/ — механизм Easyroll, декор молдинг, три слоя ППУ HR. Для офиса и дома.
Обливион (диван): https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/oblivion/ — металлические опоры.
Руан: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/ruan/ — механизм Пума, стальной декор подлокотника, низкая модульная система. Для лофт/минимализм.
Ноубл (диван): https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/noble/ — декор "канат", 4 слоя ППУ, без механизма. Для кабинета/гостиной.
Бельдомо (диван): https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/beldomo/ — механизм Relax, форма "пузырьки шоколада", регулируемый подголовник.
Эклипс: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/eclipse/ — механизм пантограф, скрытые опоры, обтекаемый дизайн. Варианты: классический или Сенс.
Нави: https://andrea-mebel.ru/catalog/sofas-i-armchairs/sofas/navi/ — механизм Тик-Так, высокие опоры, анатомическая посадка. Варианты: классический или Сенс.

--- КРЕСЛА ---
https://andrea-mebel.ru/catalog/sofas-i-armchairs/armchairs/
Космо: https://andrea-mebel.ru/catalog/sofas-i-armchairs/armchairs/cosmo/ — поворот на 360°, каркас фанера, обивка Grass, опоры сталь чёрные, нагрузка до 100 кг.
Отто: https://andrea-mebel.ru/catalog/sofas-i-armchairs/armchairs/otto/ — спинка переходит в ножки, отстрочка нитью, опоры чёрная эмаль, размеры 58×63×75 см, нагрузка 120 кг.
Мадрид: https://andrea-mebel.ru/catalog/sofas-i-armchairs/armchairs/kreslo-madrid/ — округлая форма, двойная подушка (эффект погружения), размеры 84×85×90 см, нагрузка 120 кг.

--- КРОВАТИ ---
https://andrea-mebel.ru/catalog/spalnie-gruppi/beds/
Бельдомо: https://andrea-mebel.ru/catalog/spalnie-gruppi/beds/beldomo_bed/ — мягкое изголовье, современный дизайн.
Империя: https://andrea-mebel.ru/catalog/spalnie-gruppi/beds/imperiya/ — металлические опоры, подъёмный механизм (опция), длина 207 см, ширина 167/187/207 см.
Лили: https://andrea-mebel.ru/catalog/spalnie-gruppi/beds/lili/ — детская, мягкие бортики, подъёмный механизм, 200×80/90 см.
Тео: https://andrea-mebel.ru/catalog/spalnie-gruppi/beds/teo/ — детская, мягкие бортики, выдвижной ящик, 200×80/90 см.

--- КОРПУСНАЯ МЕБЕЛЬ И СТОЛЫ ---
https://andrea-mebel.ru/catalog/korpusnaya-mebel-i-stoly/
Ноубл (тумба): https://andrea-mebel.ru/catalog/korpusnaya-mebel-i-stoly/korpusnaya-mebel/tumba-noble/ — шпон американского ореха микст, округлая, 180×55×79 см, опоры черный муар.
Обливион (стол): https://andrea-mebel.ru/catalog/korpusnaya-mebel-i-stoly/stoly/stoblivion/ — двухъярусный шпон, 123×123×37 см, опоры mat black.
Коузи (столик): https://andrea-mebel.ru/catalog/korpusnaya-mebel-i-stoly/stoly/stcozy/ — керамогранит, диаметр 600 мм, опоры металл.

--- ПУФЫ ---
https://andrea-mebel.ru/catalog/malie-formi/pufi/
Стоун: https://andrea-mebel.ru/catalog/malie-formi/pufi/stone/ — трапеция, ППУ, 870×650×440, нагрузка 100 кг.
Боно: https://andrea-mebel.ru/catalog/malie-formi/pufi/bono/ — круглый, металлическое кольцо, ППУ, 600×600×420.

--- ЛЮСТРЫ ---
https://andrea-mebel.ru/catalog/svet/lustry/
Мадрид: https://andrea-mebel.ru/catalog/svet/lustry/lustramadrid/ — дерево, высота 45 см, диаметр 30/40/50 см. Для сканди/эко/минимализм.

--- ДЕКОРАТИВНЫЕ ПОДУШКИ ---
https://andrea-mebel.ru/catalog/accessories/decorativnie-podushki/
Модели: 42×42, 42×42 с кантом, 50×50, 52×52 с кантом, 52×52×7 с кантом, 52×52 Монако, 43×43 с отстрочкой, 58×26 с отстрочкой, 60×30 с кантом. Все со съёмным чехлом.

=== ИНФОРМАЦИЯ О ФАБРИКЕ ===
Фабрика ANDREA — Ульяновск, с 1996 года. Площадь производства 30 000 кв.м., более 300 специалистов. Итальянский дизайн, фабричное качество. Сайт: https://andrea-mebel.ru/ Телефон: +7 (8422) 28-34-04
"""


KALINKA_SOFAQAS = """
=== КАТАЛОГ МЯГКОЙ МЕБЕЛИ КАЛИНКА ===

--- ДИВАНЫ ---
Калинка К26: прямой диван с регулируемыми подлокотниками и спинками, металлические опоры черные, основание массив граб, ППУ+Memory.
Калинка К28: прямой диван, механизм трансформации еврокнижка, ящик для белья.
Калинка К29: угловой диван, модульный, различные комплектации.
Калинка К30: прямой диван с подлокотниками, мягкое основание.
Калинка К31: прямой диван, высокие опоры.
Grand Sofa: большой прямой диван, мягкие подлокотники, ППУ повышенной плотности.
Lario: угловой диван с шезлонгом, регулируемые подголовники.
Soft Dream: мягкий диван с округлыми формами.
Домус: классический диван с деревянными подлокотниками.

--- КРОВАТИ ---
Вега: 160×200, 180×200, 200×200, с коробом и без, фанера берёзовая, ортопедическое основание.
Лира: 160×200, 180×200, усиленное основание, отстегивающаяся подушка в изголовье, высокие опоры 15см.
Латона: 160×200, 180×200, мягкое изголовье, подъёмный механизм.
Лига: 160×200, 180×200, с коробом.
Мира: современный дизайн, мягкое изголовье.
Эльбрус: 160×200, 180×200, 200×200, усиленное основание.

--- КРЕСЛА ---
Аляска: кресло-качалка с поворотом на 360°, без подлокотников, механизм реклайнера.
Бриз: кресло с подлокотниками, мягкое, механизм реклайнера.
Кашемир: кресло повышенной комфортности, мягкие подушки.
Силуэт: кресло современного дизайна.
Шарм: кресло с мягким сиденьем.

=== КАТАЛОГ МЯГКОЙ МЕБЕЛИ ОПРАЙМ ===

--- КРЕСЛА ---
Мэттью: кресло на поворотной опоре, габариты 1000×970×1000мм, нагрузка 110кг.
Мальви: кресло с подлокотниками, мягкое.
Ричмонд: кресло в классическом стиле.
Монако: кресло современное, компактное.
Меркурий: кресло с высокой спинкой.
Мэтью Софт: мягкая версия кресла Мэтью.

--- ДИВАНЫ ---
Симпл: прямой диван, механизм трансформации.
Симпл 2: угловая версия.
Симпл 3: трехместный.
Симпл 4: четырёхместный.
Сnof: современный диван с подлокотниками.
Портер: прямой диван с ящиком для бейтья.
Пол: компактный диван.
Тэйлор: диван с высокими опорами.
Грант: большой диван.
Флин: диван в английском стиле.

--- КРОВАТИ ---
Вега (Опрайм): кровать с мягким изголовьем.
Уно: кровать с подъёмным механизмом.
"""


def extract_short_info(txt_path: Path) -> str:
    text = txt_path.read_text(encoding="utf-8")
    lines = text.split("\n")[:50]
    return "\n".join(
        line.strip() for line in lines if line.strip() and "PAGE" not in line
    )


def main():
    base = Path("E:/ТГ-агент")

    kalinka = base / "Калинка МФ"
    opraim = base / "Опрайм"

    full_catalog = KALINKA_SOFAQAS + "\n\n" + ANDREA_CATALOG

    output = Path("E:/ТГ-агент/furniture_catalog.txt")
    output.write_text(full_catalog, encoding="utf-8")
    print(f"Saved to {output}")

    output_json = Path("E:/ТГ-агент/furniture_catalog.json")
    output_json.write_text(
        json.dumps({"catalog": full_catalog}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved to {output_json}")


if __name__ == "__main__":
    main()

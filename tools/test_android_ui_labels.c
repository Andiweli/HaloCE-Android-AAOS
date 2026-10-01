/* Run: cc -std=c99 -Wall -Wextra -Werror -fshort-wchar
   tools/test_android_ui_labels.c -o /tmp/halo-ui-test && /tmp/halo-ui-test */
#include <stdio.h>
#include "../source/interface/android_ui_labels.h"

static int equal(wchar_t const *a, wchar_t const *b)
{
	while (*a && *a == *b) { a++; b++; }
	return *a == *b;
}

#define CHECK(expression) do { if (!(expression)) { \
	fprintf(stderr, "Label regression at line %d\n", __LINE__); return 1; } } while (0)

int main(void)
{
	wchar_t buffer[128];
	wchar_t const *long_label = L"X = Jump";
#define CLEAN(text, button) android_ui_clean_label(text, buffer, 128, button)
	CHECK(equal(CLEAN(L"X = Jump", 0), L"X   Jump"));
	CHECK(equal(CLEAN(L"  A=Accept", 0), L"  A Accept"));
	CHECK(equal(CLEAN(L"Start\t=\tPause", 0), L"Start\t \tPause"));
	CHECK(equal(CLEAN(L"X = Nachladen\nB = Zurück", 0), L"X   Nachladen\nB   Zurück"));
	CHECK(equal(CLEAN(L"RT = Fire\r\nLT = Grenade", 0), L"RT   Fire\r\nLT   Grenade"));
	CHECK(equal(CLEAN(L"X\u00a0=\u00a0Jump", 0), L"X\u00a0 \u00a0Jump"));
	CHECK(equal(CLEAN(L"= Back", 1), L"  Back"));
	CHECK(equal(CLEAN(L" = ", 1), L"   "));
	CHECK(equal(CLEAN(L"= Back", 0), L"= Back"));
	CHECK(equal(CLEAN(L"Score = 10", 0), L"Score = 10"));
	CHECK(equal(CLEAN(L"X == Y", 0), L"X == Y"));
	CHECK(equal(CLEAN(L"==", 1), L"=="));
	CHECK(equal(CLEAN(L"", 1), L""));
	CHECK(android_ui_clean_label(long_label, buffer, 4, 0) == long_label);
    { wchar_t icon[] = L" =Jump";
      CHECK(equal(android_ui_after_button(icon), L"  Jump")); }
    { wchar_t icon[] = L" Jump";
      CHECK(equal(android_ui_after_button(icon), L" Jump")); }
    { wchar_t icon[] = L" == Jump";
      CHECK(equal(android_ui_after_button(icon), L" == Jump")); }
    { wchar_t icon[] = L" =";
      CHECK(equal(android_ui_after_button(icon), L"  ")); }
    CHECK(equal(android_ui_clean_label(L"A=ACCEPT   B=BACK", buffer, 256, 0), L"A ACCEPT   B BACK"));
    puts("19 Android UI label checks passed (16-bit wchar_t).");
    return 0;
}

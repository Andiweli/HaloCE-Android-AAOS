/* Android-only presentation helpers. Never change cached tags or user text. */
#ifndef HALO_ANDROID_UI_LABELS_H
#define HALO_ANDROID_UI_LABELS_H

#include <stddef.h>

static int android_ui_label_space(wchar_t c)
{
	return c == L' ' || c == L'\t' || c == 0x00a0;
}

/* The icon renderer works on its private, writable label copy. */
static wchar_t *android_ui_after_button(wchar_t *text)
{
    wchar_t *separator = text;
    while (android_ui_label_space(*separator)) separator++;
    if (*separator == L'=' && separator[1] != L'=') *separator = L' ';
    return text;
}

static int android_ui_button_name(wchar_t const *start, wchar_t const *end)
{
	static wchar_t const *const names[] = {
		L"A", L"B", L"X", L"Y", L"L", L"R", L"LT", L"RT", L"LB", L"RB",
		L"L1", L"L2", L"L3", L"R1", L"R2", L"R3", L"LS", L"RS",
		L"START", L"BACK", L"WHITE", L"BLACK", L"D-PAD"
	};
	size_t i;
	for (i = 0; i < sizeof(names) / sizeof(names[0]); i++)
	{
		wchar_t const *a = start, *b = names[i];
		while (a != end && *b)
		{
			wchar_t c = *a;
			if (c >= L'a' && c <= L'z') c -= L'a' - L'A';
			if (c != *b) break;
			a++;
			b++;
		}
		if (a == end && !*b) return 1;
	}
	return 0;
}

/* Only asset-backed labels use this function. Dynamic profile names,
   server names and editable fields must bypass it. Returns the original
   on insufficient scratch space, without truncating the displayed text. */
static wchar_t const *android_ui_clean_label(wchar_t const *text,
	wchar_t *buffer, size_t capacity, int follows_button)
{
	size_t length = 0;
	wchar_t const *read = text;
	wchar_t *write = buffer;
	int line_start = 1;
	while (text[length]) length++;
	if (length >= capacity) return text;
	while (*read)
	{
		if (line_start)
		{
			wchar_t const *start = read, *end, *separator;
			while (android_ui_label_space(*start)) start++;
			end = start;
			while (*end && !android_ui_label_space(*end) && *end != L'='
				&& *end != L'\r' && *end != L'\n') end++;
			separator = end;
			while (android_ui_label_space(*separator)) separator++;
            if ((follows_button && *start == L'=' && start[1] != L'=') ||
                (*separator == L'=' && separator[1] != L'=' && android_ui_button_name(start, end)))
            {
                wchar_t const *equals = follows_button && *start == L'=' ? start : separator;
                while (read < equals) *write++ = *read++;
                *write++ = L' ';
                read++;
            }
			line_start = 0;
			if (!*read) break;
		}
		if (*read == L'\r' || *read == L'\n' || android_ui_label_space(*read)) line_start = 1;
		*write++ = *read++;
	}
	*write = 0;
	return buffer;
}

#endif

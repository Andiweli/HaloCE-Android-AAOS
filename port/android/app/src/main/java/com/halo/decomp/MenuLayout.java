package com.halo.decomp;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.GridLayout;
import android.widget.LinearLayout;

/** Menu rows respond to their measured space, including split windows and larger system text
 * (from CubeEvil4-Android's in-game menu, as SettingsOverlay takes its look). */
final class MenuLayout {
  private MenuLayout() {}

  private static int dp(Context context, float value) {
    return Math.round(value * context.getResources().getDisplayMetrics().density);
  }

  /** Half the gap between two buttons, in dp: each button's margin on all four sides. */
  static final int GAP = 7;

  /**
   * Equal-width buttons; long translations reduce the column count before their text needs more than
   * `lines` lines.
   */
  static final class Buttons extends GridLayout {
    private final int maxColumns, lines;
    private int measuredColumns;

    Buttons(Context context, int maxColumns) {
      this(context, maxColumns, 1);
    }

    Buttons(Context context, int maxColumns, int lines) {
      super(context);
      this.maxColumns = maxColumns;
      this.lines = lines;
      setAlignmentMode(ALIGN_MARGINS);
    }

    void addButton(View button) {
      LayoutParams lp = new LayoutParams();
      lp.width = 0;
      lp.height = LayoutParams.WRAP_CONTENT;
      lp.setMargins(dp(getContext(), GAP), dp(getContext(), GAP), dp(getContext(), GAP), dp(getContext(), GAP));
      addView(button, lp);
    }

    /** An empty cell (a pair with one setting): it keeps its place while the row has all its columns and goes
     *  away when a narrow window folds the row, so no hole is left there; the focus never stops on it. */
    void addGap() {
      View gap = new View(getContext());
      gap.setTag(GAP_TAG);
      gap.setFocusable(false);
      gap.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
      gap.setVisibility(View.INVISIBLE);
      addButton(gap);
    }

    private static boolean isGap(View v) {
      return GAP_TAG.equals(v.getTag());
    }

    @Override protected void onMeasure(int widthSpec, int heightSpec) {
      int available = Math.max(1, MeasureSpec.getSize(widthSpec) - getPaddingLeft() - getPaddingRight());
      int needed = dp(getContext(), 64);
      for (int i = 0; i < getChildCount(); i++) {
        View child = getChildAt(i);
        child.measure(MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED),
            MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED));
        if (isGap(child)) continue;
        int padding = child.getPaddingLeft() + child.getPaddingRight();
        int text = child.getMeasuredWidth() - padding;
        needed = Math.max(needed, (text + lines - 1) / lines + padding + dp(getContext(), 2 * GAP));
      }
      int columns = Math.max(1, Math.min(Math.min(maxColumns, getChildCount()), available / needed));
      // Clear auto-assigned spans before changing column count (also supports resizing back up).
      if (measuredColumns != columns) {
        setColumnCount(UNDEFINED);
        setRowCount(UNDEFINED);
        int cell = 0;
        for (int i = 0; i < getChildCount(); i++) {
          View child = getChildAt(i);
          if (isGap(child)) {
            // an empty cell only while the row has all its columns
            boolean keep = columns == maxColumns;
            child.setVisibility(keep ? View.INVISIBLE : View.GONE);
            if (!keep) continue;
          }
          LayoutParams lp = (LayoutParams) child.getLayoutParams();
          lp.columnSpec = spec(cell % columns, FILL, 1f);
          lp.rowSpec = spec(cell / columns, FILL);
          child.setLayoutParams(lp);
          cell++;
        }
        setColumnCount(columns);
        setRowCount(Math.max(1, (cell + columns - 1) / columns));
        measuredColumns = columns;
      }
      super.onMeasure(widthSpec, heightSpec);
    }
  }

  private static final String GAP_TAG = "MenuLayout.gap";

  /** Two columns when there is room, otherwise a vertical stack. Negative fixedWidth fixes the end. */
  static final class Columns extends LinearLayout {
    private final int fixedWidth, minimumWidth;
    private final boolean emptyCaption;
    private boolean fillEndHeight;
    private float startWeight, endWeight;

    Columns(Context context, int fixedWidth, int minimumWidth, boolean emptyCaption) {
      super(context);
      this.fixedWidth = fixedWidth;
      this.minimumWidth = minimumWidth;
      this.emptyCaption = emptyCaption;
      setBaselineAligned(false);
    }

    /** In two-column mode the end column fills the height set by the taller content. */
    void setFillEndHeight(boolean fill) {
      fillEndHeight = fill;
      requestLayout();
    }

    /** In two-column mode the columns share the width start : end instead of a fixed start column. */
    void setWeights(float start, float end) {
      startWeight = start;
      endWeight = end;
      requestLayout();
    }

    @Override protected void onMeasure(int widthSpec, int heightSpec) {
      float textScale = Math.max(1f, getResources().getConfiguration().fontScale);
      boolean sideBySide = MeasureSpec.getSize(widthSpec) >= dp(getContext(), minimumWidth * textScale);
      setOrientation(sideBySide ? HORIZONTAL : VERTICAL);
      if (emptyCaption && getChildCount() > 0) getChildAt(0).setVisibility(sideBySide ? VISIBLE : GONE);
      for (int i = 0; i < getChildCount(); i++) {
        View child = getChildAt(i);
        LayoutParams lp = (LayoutParams) child.getLayoutParams();
        boolean fixed = fixedWidth > 0 ? i == 0 : fixedWidth < 0 && i == getChildCount() - 1;
        lp.width = sideBySide ? (fixed ? dp(getContext(), Math.abs(fixedWidth) * textScale) : 0)
            : LayoutParams.MATCH_PARENT;
        lp.height = sideBySide && fillEndHeight && i == getChildCount() - 1
            ? LayoutParams.MATCH_PARENT : LayoutParams.WRAP_CONTENT;
        lp.weight = sideBySide && !fixed ? 1 : 0;
        if (sideBySide && startWeight > 0) {
          lp.width = 0;
          lp.weight = i == 0 ? startWeight : endWeight;
        }
      }
      super.onMeasure(widthSpec, heightSpec);
    }
  }

  /** Back / title / resume in one row; narrow windows put the title above the two actions. */
  static final class Header extends ViewGroup {
    private boolean horizontal, noteBelow;
    private final View back, title, note, resume;

    Header(Context context, View back, View title, View resume) {
      this(context, back, title, null, resume);
    }

    Header(Context context, View back, View title, View note, View resume) {
      super(context);
      this.back = back;
      this.title = title;
      this.note = note;
      this.resume = resume;
      addView(back); addView(title);
      if (note != null) addView(note);
      addView(resume);
    }

    private boolean hasNote() { return note != null && note.getVisibility() != GONE; }

    private int actionsHeight() {
      return Math.max(back.getVisibility() == GONE ? 0 : back.getMeasuredHeight(), resume.getMeasuredHeight());
    }

    @Override protected void onMeasure(int widthSpec, int heightSpec) {
      int width = MeasureSpec.getSize(widthSpec), gap = dp(getContext(), 16), noteGap = dp(getContext(), 18);
      float textScale = Math.max(1f, getResources().getConfiguration().fontScale);
      horizontal = width >= dp(getContext(), 680 * textScale);
      int actionsWidth = Math.max(1, (width - gap) / 2);
      int actionSpec = MeasureSpec.makeMeasureSpec(actionsWidth, MeasureSpec.AT_MOST);
      int freeHeight = MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED);
      if (back.getVisibility() != GONE) back.measure(actionSpec, freeHeight);
      int backWidth = back.getVisibility() == GONE ? 0 : back.getMeasuredWidth() + gap;
      int noteWidth = 0;
      if (hasNote()) {
        note.measure(MeasureSpec.makeMeasureSpec(width, MeasureSpec.AT_MOST), freeHeight);
        noteWidth = note.getMeasuredWidth() + noteGap;
      }
      // beside the title half the width; under it (a narrow window) what the back button leaves of the row, so
      // "Back to the game" and the update button do not break letter by letter
      resume.measure(horizontal ? actionSpec
          : MeasureSpec.makeMeasureSpec(Math.max(1, width - backWidth), MeasureSpec.AT_MOST), freeHeight);
      noteBelow = hasNote() && !horizontal && backWidth + noteWidth + resume.getMeasuredWidth() > width;
      int titleWidth = horizontal ? Math.max(1, width - backWidth - resume.getMeasuredWidth() - gap - noteWidth) : width;
      title.measure(MeasureSpec.makeMeasureSpec(titleWidth, MeasureSpec.EXACTLY), freeHeight);
      int actionsHeight = Math.max(actionsHeight(), hasNote() && !noteBelow ? note.getMeasuredHeight() : 0);
      int height = horizontal ? Math.max(title.getMeasuredHeight(), actionsHeight)
          : title.getMeasuredHeight() + dp(getContext(), 8) + actionsHeight
              + (noteBelow ? dp(getContext(), 4) + note.getMeasuredHeight() : 0);
      setMeasuredDimension(width, resolveSize(height, heightSpec));
    }

    private void place(View child, int start, int top) {
      int left = getLayoutDirection() == LAYOUT_DIRECTION_RTL ? getWidth() - start - child.getMeasuredWidth() : start;
      child.layout(left, top, left + child.getMeasuredWidth(), top + child.getMeasuredHeight());
    }

    @Override protected void onLayout(boolean changed, int left, int top, int right, int bottom) {
      int titleStart = back.getVisibility() == GONE ? 0 : back.getMeasuredWidth() + dp(getContext(), 16);
      int actionsTop = horizontal ? 0 : title.getMeasuredHeight() + dp(getContext(), 8);
      if (back.getVisibility() != GONE) place(back, 0, horizontal ? (getHeight() - back.getMeasuredHeight()) / 2 : actionsTop);
      place(title, horizontal ? titleStart : 0, horizontal ? (getHeight() - title.getMeasuredHeight()) / 2 : 0);
      place(resume, getWidth() - resume.getMeasuredWidth(), horizontal ? (getHeight() - resume.getMeasuredHeight()) / 2 : actionsTop);
      if (hasNote()) {
        int noteWidth = note.getMeasuredWidth(), noteHeight = note.getMeasuredHeight();
        if (noteBelow) {
          place(note, getWidth() - noteWidth, actionsTop + actionsHeight() + dp(getContext(), 4));
        } else {
          int start = getWidth() - resume.getMeasuredWidth() - dp(getContext(), 18) - noteWidth;
          place(note, start, horizontal ? (getHeight() - noteHeight) / 2
              : actionsTop + (resume.getMeasuredHeight() - noteHeight) / 2);
        }
      }
    }
  }
}

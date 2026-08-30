/* Reusable controller for future OpenSAT Visualize question timers.
 * The caller must keep question content behind renderQuestion(); it is not
 * inserted into the visible document until Start is clicked.
 */
(function attachOpenSATTimer(global) {
  "use strict";

  function createQuestionTimer(options) {
    const { startButton, stopButton, timerOutput, questionHost, renderQuestion } = options;
    let state = "locked";
    let startedAt = null;
    let elapsedMilliseconds = 0;
    let intervalId = null;

    function elapsed() {
      return state === "running"
        ? elapsedMilliseconds + (performance.now() - startedAt)
        : elapsedMilliseconds;
    }

    function paint() {
      timerOutput.textContent = `${(elapsed() / 1000).toFixed(1)} s`;
    }

    function start() {
      if (state !== "locked") return;
      renderQuestion(questionHost);
      state = "running";
      startedAt = performance.now();
      startButton.disabled = true;
      stopButton.disabled = false;
      intervalId = global.setInterval(paint, 100);
      paint();
    }

    function stop() {
      if (state !== "running") return;
      elapsedMilliseconds = elapsed();
      startedAt = null;
      state = "stopped";
      global.clearInterval(intervalId);
      intervalId = null;
      stopButton.disabled = true;
      paint();
      // Deliberately keep the rendered question and selected answer visible.
    }

    startButton.addEventListener("click", start);
    stopButton.addEventListener("click", stop);
    stopButton.disabled = true;
    questionHost.replaceChildren();
    paint();

    return {
      snapshot() {
        return {
          time_seconds: Number((elapsed() / 1000).toFixed(3)),
          timing_source: "visualize_monotonic_timer",
          timer_state: state,
        };
      },
    };
  }

  global.OpenSATQuestionTimer = { createQuestionTimer };
})(window);

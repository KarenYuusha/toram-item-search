window.Streamlit = (function () {
  const RENDER_EVENT = "streamlit:render";
  const events = new EventTarget();
  let lastFrameHeight = null;
  let registeredMessageListener = false;

  function sendBackMsg(type, data) {
    window.parent.postMessage({
      isStreamlitMessage: true,
      type,
      ...data,
    }, "*");
  }

  function onMessageEvent(event) {
    if (!event.data || event.data.type !== RENDER_EVENT) {
      return;
    }

    const renderEvent = new CustomEvent(RENDER_EVENT, {
      detail: {
        args: event.data.args || {},
        disabled: Boolean(event.data.disabled),
        theme: event.data.theme,
      },
    });
    events.dispatchEvent(renderEvent);
  }

  function setComponentReady() {
    if (!registeredMessageListener) {
      window.addEventListener("message", onMessageEvent);
      registeredMessageListener = true;
    }

    sendBackMsg("streamlit:componentReady", { apiVersion: 1 });
  }

  function setFrameHeight(height) {
    const nextHeight = height || document.body.scrollHeight;
    if (nextHeight === lastFrameHeight) {
      return;
    }

    lastFrameHeight = nextHeight;
    sendBackMsg("streamlit:setFrameHeight", { height: nextHeight });
  }

  function setComponentValue(value) {
    sendBackMsg("streamlit:setComponentValue", {
      value,
      dataType: "json",
    });
  }

  return {
    RENDER_EVENT,
    events,
    setComponentReady,
    setFrameHeight,
    setComponentValue,
  };
}());

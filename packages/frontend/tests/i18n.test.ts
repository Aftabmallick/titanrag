import { test, describe } from "node:test";
import assert from "node:assert/strict";
import enMessages from "../src/messages/en.json";
import esMessages from "../src/messages/es.json";
import deMessages from "../src/messages/de.json";

describe("i18n Catalogs & Dictionary Parity", () => {
  test("all languages contain required root sections", () => {
    const requiredSections = ["nav", "chat", "documents", "settings", "common"];
    for (const section of requiredSections) {
      assert.ok(section in enMessages, `Missing section '${section}' in en.json`);
      assert.ok(section in esMessages, `Missing section '${section}' in es.json`);
      assert.ok(section in deMessages, `Missing section '${section}' in de.json`);
    }
  });

  test("navigation items have exact parity across en, es, de", () => {
    const enNavKeys = Object.keys(enMessages.nav);
    const esNavKeys = Object.keys(esMessages.nav);
    const deNavKeys = Object.keys(deMessages.nav);

    assert.deepEqual(esNavKeys.sort(), enNavKeys.sort(), "ES nav keys mismatch with EN");
    assert.deepEqual(deNavKeys.sort(), enNavKeys.sort(), "DE nav keys mismatch with EN");
  });

  test("chat actions have parity across all languages", () => {
    const enChatKeys = Object.keys(enMessages.chat);
    const esChatKeys = Object.keys(esMessages.chat);
    const deChatKeys = Object.keys(deMessages.chat);

    for (const k of enChatKeys) {
      assert.ok(k in esMessages.chat, `Missing chat key '${k}' in es.json`);
      assert.ok(k in deMessages.chat, `Missing chat key '${k}' in de.json`);
    }
  });

  test("settings tabs are translated across all languages", () => {
    assert.equal(typeof enMessages.settings.searchTab, "string");
    assert.equal(typeof esMessages.settings.searchTab, "string");
    assert.equal(typeof deMessages.settings.searchTab, "string");
  });
});

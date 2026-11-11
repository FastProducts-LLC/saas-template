import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ROUTES } from "../../../shared/lib/routes";
import { isApiErrorWithCode } from "../../../shared/api";
import { COMMUNITY_MESSAGE_MAX_LENGTH } from "../../../shared/lib/policy";
import { relativeTime } from "../../../shared/lib/time";
import { Avatar, Button, Spinner, Textarea, ErrorAlert } from "../../../shared/ui";
import {
  useConversations,
  useMarkConversationRead,
  useMessages,
  useMyCommunity,
  useSendMessage,
} from "../api/hooks";
import type { Conversation, Message } from "../model/types";

function ConversationRow({
  conversation,
  active,
}: {
  conversation: Conversation;
  active: boolean;
}) {
  const name = conversation.other?.display_name ?? "Deleted member";
  return (
    <Link
      to={ROUTES.community.conversation(conversation.id)}
      data-testid="community-conversation-row"
      data-id={conversation.id}
      className={`flex items-center gap-3 border-b border-[var(--line)] px-4 py-3 transition-colors ${
        active ? "bg-[var(--mist)]" : "hover:bg-[var(--paper)]"
      }`}
    >
      <Avatar name={name} src={conversation.other?.avatar_url} size="md" />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <p className="truncate text-sm font-semibold text-[var(--ink)]">{name}</p>
          {conversation.last_message_at && (
            <span className="shrink-0 font-[family-name:var(--font-mono)] text-[11px] text-[var(--slate)]/60">
              {relativeTime(conversation.last_message_at)}
            </span>
          )}
        </div>
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-[13px] text-[var(--slate)]/75">
            {conversation.last_message_preview ?? "No messages yet"}
          </p>
          {conversation.unread_count > 0 && (
            <span
              data-testid="community-unread-count"
              className="shrink-0 rounded-[2px] border border-[var(--teal-deep)] px-1 font-[family-name:var(--font-mono)] text-[11px] font-medium tabular-nums text-[var(--teal-deep)]"
            >
              {conversation.unread_count}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

function MessageBubble({ message }: { message: Message }) {
  return (
    <div
      data-testid="community-message"
      className={`flex ${message.mine ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[75%] border px-3 py-2 text-sm ${
          message.mine
            ? "border-[var(--ink)] bg-[var(--ink)] text-white"
            : "border-[var(--line)] bg-white text-[var(--ink)]"
        }`}
        style={{ borderRadius: 4 }}
      >
        <p
          className={
            message.deleted
              ? "italic opacity-60"
              : // [overflow-wrap:anywhere]: unbroken runs (URLs, pasted
                // tokens) must wrap, or one message stretches the whole page.
                "whitespace-pre-wrap [overflow-wrap:anywhere]"
          }
        >
          {message.deleted ? "Message removed" : message.body}
        </p>
        <p
          className={`mt-1 font-[family-name:var(--font-mono)] text-[11px] tabular-nums ${
            message.mine ? "text-white/60" : "text-[var(--slate)]/60"
          }`}
        >
          {relativeTime(message.created_at)}
        </p>
      </div>
    </div>
  );
}

function Thread({ conversationId }: { conversationId: string }) {
  const navigate = useNavigate();
  const { data: me } = useMyCommunity();
  const { data: page, isLoading } = useMessages(conversationId);
  const send = useSendMessage(conversationId);
  const markRead = useMarkConversationRead();
  const [body, setBody] = useState("");
  const [error, setError] = useState<unknown>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastMarkedRef = useRef<string | null>(null);

  const isPremium = me?.membership?.is_premium ?? false;
  // API returns newest first; render oldest → newest.
  const messages = [...(page?.items ?? [])].reverse();
  const newestId = messages.at(-1)?.id ?? null;

  // Mark read whenever a new latest message is visible.
  useEffect(() => {
    if (newestId && lastMarkedRef.current !== newestId) {
      lastMarkedRef.current = newestId;
      markRead.mutate(conversationId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, newestId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [newestId]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) return;
    setError(null);
    send.mutate(trimmed, {
      onSuccess: () => setBody(""),
      onError: (err: unknown) => {
        if (isApiErrorWithCode(err, "ERR_COMM_004")) {
          navigate(ROUTES.community.upgrade);
        } else {
          setError(err);
        }
      },
    });
  };

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col" data-testid="community-thread">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <p className="pt-10 text-center text-sm text-[var(--slate)]/60">
            No messages yet — say hello.
          </p>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-[var(--line)] p-4">
        {!!error && <ErrorAlert error={error} className="mb-2" />}
        {isPremium ? (
          <form onSubmit={submit} className="flex items-end gap-3">
            <div className="flex-1">
              <Textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    submit(e);
                  }
                }}
                rows={2}
                maxLength={COMMUNITY_MESSAGE_MAX_LENGTH}
                placeholder="Write a message… (Enter to send)"
                data-testid="community-composer"
              />
            </div>
            <Button type="submit" loading={send.isPending} data-testid="community-send">
              Send
            </Button>
          </form>
        ) : (
          <div
            data-testid="community-composer-upgrade"
            className="flex items-center justify-between gap-4 bg-[var(--mist)] px-4 py-3"
            style={{ borderRadius: 4 }}
          >
            <p className="text-sm text-[var(--slate)]">
              Replying is part of the premium membership.
            </p>
            <Link
              to={ROUTES.community.upgrade}
              className="whitespace-nowrap text-sm font-semibold text-[var(--teal-deep)] hover:underline"
            >
              See plans →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

export default function MessagesPage() {
  const { conversationId } = useParams<{ conversationId: string }>();
  const { data: conversations, isLoading } = useConversations({ poll: true });

  return (
    <div className="gd-page-in" data-testid="community-messages-page">
      <div className="flex items-baseline justify-between">
        <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold text-[var(--ink)]">
          Messages
        </h1>
        <Link
          to={ROUTES.community.list}
          className="text-sm font-medium text-[var(--teal-deep)] hover:underline"
        >
          ← Directory
        </Link>
      </div>

      <div
        className="mt-6 flex overflow-hidden border border-[var(--line)] bg-white"
        style={{ borderRadius: 4, height: "calc(100vh - 220px)", minHeight: 360 }}
      >
        <aside className="w-72 shrink-0 overflow-y-auto border-r border-[var(--line)]">
          {isLoading && (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          )}
          {conversations?.map((c) => (
            <ConversationRow key={c.id} conversation={c} active={c.id === conversationId} />
          ))}
          {conversations?.length === 0 && (
            <p
              data-testid="community-conversations-empty"
              className="px-4 py-8 text-center text-sm text-[var(--slate)]/60"
            >
              No conversations yet. Find someone in the directory to start one.
            </p>
          )}
        </aside>

        {conversationId ? (
          <Thread conversationId={conversationId} />
        ) : (
          <div className="flex flex-1 items-center justify-center text-sm text-[var(--slate)]/60">
            Select a conversation
          </div>
        )}
      </div>
    </div>
  );
}

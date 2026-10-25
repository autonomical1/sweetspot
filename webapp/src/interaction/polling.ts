export function shouldPoll(stage: string, visible: boolean, edited: boolean): boolean {
  return visible && !edited && (stage === 'quick' || stage === 'refining');
}
